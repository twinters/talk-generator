# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

talkgenerator 5 brings the 2019 generator up to date. Language models write the talks (OpenRouter's free models,
at no cost), Claude can write them too, talks come in themes and stream into the browser, and every talk is a deck,
plain JSON data that the PowerPoint is drawn from. 4.x's command line and settings keep working:
[Migrating from 4.x](https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md) says what
changes, and the README and the [docs](https://github.com/twinters/talk-generator/tree/master/docs) cover the rest.
The design is in [docs/v5-plan.md](https://github.com/twinters/talk-generator/blob/master/docs/v5-plan.md).

### Language models write the talks

- talkgenerator still picks every slide with the talk's seed, and a language model writes what goes on them, in one
  streamed request per talk: the title, the presenter's job and name, a thesis, and every slide in order, with
  callbacks to earlier slides. A slide the model gets wrong, whose images can't be found or that repeats one before
  it comes from the classic generator, and so does the whole talk when the model fails, isn't there, or finds the
  topic unsafe (it's asked once more first, as free models turned down "penguins"). The presenter's name you give
  never reaches the model, and the same seed with the same answers gives the same talk.
- Providers, with their SDKs as extras (`talkgenerator[openai]`, `talkgenerator[anthropic]`, or `talkgenerator[llm]`
  for both): `openrouter` (OpenRouter's free router, or `openrouter:<model>[,<fallback>...]`), `anthropic` (Claude
  Opus 5.5, or `anthropic:<model>`), `openai:<model>`, `chatgpt` (the models of your ChatGPT plan), and
  `replay:<cassette.json>` (answers recorded earlier, for tests). `--llm`, `llm=` and `TALKGENERATOR_LLM` pick one;
  `--llm none` and `DISABLE_LLM=1` make classic talks.
- Free models first: without `TALKGENERATOR_LLM`, your ChatGPT plan's models write the talks once you've signed in
  with ChatGPT, else OpenRouter's free models when there's an OpenRouter key, and paid models only when `--llm` or
  `TALKGENERATOR_LLM` names them. The free models write without thinking first, which takes a talk from minutes to
  seconds; `TALKGENERATOR_LLM_EFFORT` sets how hard a model thinks.
- `talkgenerator login openrouter`: sign in to OpenRouter in the browser, and talkgenerator gets a key of its own,
  kept in your config folder (`--headless`, `--status` for the free requests left today, `logout openrouter`).
- `talkgenerator login chatgpt`: Sign in with ChatGPT (OpenAI's sign-in for open-source apps on your own computer, in
  preview), so that the models of your ChatGPT plan (Plus or Pro) write your talks, counting toward the plan's usage
  (`--status`, `--new-account`, `logout chatgpt`).
- Talks in Dutch, French, German, Spanish, Italian, Portuguese and Swedish (`--language`), with talkgenerator's own words on
  the slides in the talk's language too. A slide that doesn't come out becomes a picture without text instead of an
  English one, and recipes that find English texts, such as real quotes, are left out.
- After every talk, the logs say how many requests it made and what they cost, and so does the deck (`usage`).
  `budget=` holds a talk to a limit (a $0 budget lets only free models write it). Keys never show up in logs, error
  messages or decks.

### Claude writes talks too

- The talkgenerator Skill (`skill/`): Claude writes talks for PowerPoint karaoke and improvised TED talks as plans,
  renders them with `talkgenerator render`, and fixes them from the report. It installs as a Claude Code plugin
  straight from this repository (`/plugin marketplace add twinters/talk-generator`), or as a skill folder.
- `talkgenerator render plan.json` turns a talk plan into a PowerPoint, with the deck's JSON and a contact sheet of
  its images next to it, and prints a report in JSON: per slide, whether it came out as planned, the classic way or
  not at all, and why, and what every image was searched with, what it shows and where it's from. Texts up to an
  eighth over their length limit stay whole, a text cut shorter ends on a whole word, and an image query may name an
  image file of your own.
- `talkgenerator formats` lists the formats (`--details` the slides a plan can have, with their texts, length limits
  and recipes; `--looks` the image looks; `--licenses` the license policies), and `talkgenerator schema plan|deck`
  prints the plan and deck formats as JSON Schemas.
- `talkgenerator mcp`: a local MCP server for Claude Desktop and other MCP clients (`talkgenerator[mcp]`), with the
  tools `list_formats`, `describe_format`, `get_plan_schema`, `render_plan` and `generate_talk`. The client starts it
  on your computer, where it uses your keys and saves only in its output folder, never over a file; a tool call can't
  pick a paid model. Nothing is hosted. On Windows on Arm, the MCP SDK only installs in an x64 Python.

### Themes and layouts

- `--theme`: besides the 2019 template (`classic`), seventeen families of themes drawn as shapes on a 1920×1080
  canvas, from `clean keynote` and `dark minimal` to `hacker terminal`, `blueprint`, `chalkboard`, `newspaper` and
  `Swiss poster`, with `1997 WordArt`, `Comic Sans everywhere` and `clip-art corporate` for laughs. The talk's seed picks a member of the family: its colours (repaired until
  every text reads on its background, by WCAG's contrast rules), font pair, casing, decoration and layouts. `random`
  is the default, `--no_extreme_themes` leaves the ones for laughs out of it, `--theme chaos` gives every slide a
  theme of its own (`--style_chaos`: some of them), and `TALKGENERATOR_THEME` sets another default. A plan can have
  a `theme` too.
- Every kind of slide has its layouts (61 in all, some of them a family's own title or section slide), which put
  every text and picture in its box, give every text the largest size at which it fits, and never repeat the layout
  of the slide before when another fits.
- Every family has a decoration of its own, so that a theme is more than a font and colours
  (`talkgenerator.design.motifs`): a fixture on every slide, and its big pieces on the title and section slides. A
  hacker terminal's window bar, scanlines, prompts, a block cursor and a status line, in green or amber phosphor; a
  blueprint's grid, registration marks, dimension lines, figure plates and title block; a chalkboard's wooden frame,
  ledge with chalk and an eraser, chalk underlines and taped pictures; a newspaper's masthead rules and front page; a
  Swiss poster's grid, black rule, one red block a slide, red circle and black dividers; a kindergarten's bunting,
  crayon squiggles, confetti, sticker pictures, sun and hills (the `kids` family, reworked); academic's Beamer-like
  title band and slide dots, neon's sunset over a grid floor, vintage paper's ornamented frame, brutalist's title
  blocks and hard shadows, and the rest. The decoration is drawn with the deck's own elements, which now also have
  polygons (stars, pennants, bursts), turned shapes, rounded corners, outlines and background patterns (lines,
  grids, dots), drawn alike in PowerPoint (a pattern as the slide's background picture, shared by its slides), in
  previews and in the browser. Its texts (a slide's number, a prompt) are numbers, symbols and code, not the talk's
  words: the language and leftover checks leave them out. Texts are
  measured with the open fonts that come with talkgenerator (Liberation, Carlito, Caladea and Gelasio), which share
  the widths of Arial, Calibri, Cambria, Georgia and the rest.
- Pictures get their theme's treatment, so that pictures from mixed sources share one look: most stay as they are or
  get a gentle tint (a slight warm or cool cast, a wash of the theme's paper or accent, laid over them), and the
  strong filters (grayscale, sepia, a duotone, black and white) are for the families made for them, and only where
  they fit: a family's filter can be for the photos behind or across a whole slide only (neon, dark minimal), and
  black and white never goes behind a slide's texts. Of random themes' pictures, a fifth get a strong filter (a third
  did). Rounded corners, a polaroid frame, grain or a vignette come with some families, as PowerPoint picture effects
  ("Reset Picture" brings the original back). Some families' headings get WordArt-style effects (1997's rainbow in an
  outline, bent into a wave or an arch; neon's glow; brutalist's hard shadow), as text effects, so texts stay text.
- Themed slides animate as the 2019 template's do: two or three columns appear click by click, the one before
  dimming, and a video plays as its column appears.
- `talkgenerator.render.preview` draws decks as pictures, with a contact sheet of a whole deck, and
  `talkgenerator.design.themes.catalog()` lists the themes with a label and a description, for a settings menu.
- Open fonts in themes: every family but the three for laughs has two pairings of open fonts with more personality,
  from Google Fonts (SIL Open Font License 1.1), which a member has two times in three (`themes.OPEN_FONT_CHANCE`):
  clean keynote Barlow, and Atkinson Hyperlegible; dark minimal IBM Plex Mono over Barlow, and Titillium Web;
  corporate Poppins over Lato, and Lato; academic Crimson Text, and Spectral; startup Poppins, and Archivo Black over
  Poppins; vintage paper Abril Fatface over Crimson Text, and Courier Prime; kids Mali, and Sniglet over Mali;
  brutalist Archivo Black or Space Mono over IBM Plex Mono; neon Audiowide (never in capitals: too wide for the
  longest titles) over Chakra Petch, and Chakra Petch; hacker terminal IBM Plex Mono, Space Mono over IBM Plex Mono,
  and Courier Prime; blueprint Titillium Web over IBM Plex Mono, Chakra Petch over Titillium Web, and Barlow over IBM
  Plex Mono; chalkboard Mali, and Sniglet over Mali; newspaper Abril Fatface over Crimson Text, and Spectral; Swiss
  poster Archivo Black over Barlow, and Barlow (kids, hacker terminal and chalkboard have theirs four times in five or
  more). A member draws them after everything else, so a seed's member
  keeps its colours and the rest. They're bundled in `data/fonts` (3.9 MB, credited in its README), so they measure
  the same everywhere, and a themed .pptx carries the ones it uses inside it, regular and bold, as uncompressed
  Embedded OpenType (`talkgenerator.render.embedding`), which PowerPoint shows where they aren't installed (a deck
  grows by about 55 to 800 KB). Where a deck's own fonts aren't used (PowerPoint for the web, most likely Keynote), a
  stand-in shows: each open font has an installed one (`talkgenerator.design.fonts.OPEN_FONTS`), its texts are fitted
  to both, and its runs carry the font's PANOSE and pitch family, so the stand-in is of the same kind. Lato and
  Poppins are Office cloud fonts, which PowerPoint for the web shows anyway.

### Images

- License classes and policies: every image has a class (`public-domain`, `open` for CC BY and BY-SA, `stock`,
  `generated` or `fair-use`), and a talk's license policy picks the classes it allows (`--license_policy`: `all`, the
  default; `open`, everything but fair use; or classes, as `public-domain,open`). The `ted` format keeps to `open`,
  the image search keeps to the policy, credits name open and public domain licenses ("CC BY 2.0", linking it), and
  `talkgenerator check` reports an image the policy doesn't allow as an error.
- Images come through slots and an image finder, which searches a look's sources a few at a time, in parallel (with
  v4's caches and cooldowns), filters what they find (license, size, orientation, unsafe descriptions, images the talk
  has already), and picks with the talk's seed: the same seed finds the same images, whichever search answers first.
- Looks (aesthetic profiles), with their own sources, filters and preferences: `photo`, `calm-backdrop`, `vintage`,
  `museum`, `space-science`, `corporate-stock`, `illustration`, `meme-chaos` and more, and flavour packs of curated
  subreddits: `cursed`, `wholesome`, `bad-charts`, `medieval`, `liminal`, `retro-futurism`, `accidental-art`,
  `pareidolia` and `corporate-cringe`. `talkgenerator formats --looks` lists them.
- A look at the candidates' thumbnails (brightness, colourfulness, how gray they are, detail where the text goes,
  main colours, a perceptual hash): vintage slots prefer black and white and sepia, calm backdrops little detail
  behind the text, themed talks pictures that go with the theme's colours, and nearly the same picture doesn't come
  back on another slide. A vintage picture in colour turns sepia in a theme without a filter of its own.
- Gifs too large to embed play as Reddit's mp4 copy of them (many on r/gifs are 40 to 90 MB): the video starts by
  itself and loops without sound, as the gif would, with a still as its poster frame.
- Generated pictures (`talkgenerator.images.generation`, `talkgenerator.images.generators`): in talks a language
  model writes (and plans from the Skill or the MCP server), an image generator draws what stock photos can't show
  well: the presenter's weird hobby, the cover of the book they wrote, old photos of moments in a made-up history,
  the portrait of a made-up historical figure, a made-up news story's photo (slots with `generate`). The model writes
  a prompt for each (plans: `SlidePlan.prompts`), the slide comes with a stock photo, and the generated picture takes
  its place once it's in; a planned slide whose images can't be found at all gets generated ones on its last try.
  One `ImageGenerator` interface (a prompt, an aspect ratio, a style, what to avoid and a seed in; the picture, its
  model, its cost and moderation's flags out), with adapters for OpenAI's Image API (`openai`, gpt-image-2),
  OpenRouter's (`openrouter`), Google's Gemini (`gemini`), Black Forest Labs' FLUX (`flux`), and ComfyUI and
  Automatic1111-style servers of your own (`comfyui`, `automatic1111`), picked by `--image_generator` (also on
  `talkgenerator render`), `image_generator=` (`generate_presentation`, `stream_talk`, `render_plan`) or
  `TALKGENERATOR_IMAGE_GENERATOR`, and never because a key is set; `DISABLE_IMAGE_GENERATION=1` switches them off.
  The default models and list prices are config (`talkgenerator/data/image_generators.json`, and an
  `image_generators.json` in the config folder over it; `talkgenerator formats --generators` lists them), as image
  models come and go. A talk generates 3 pictures at most (`--generated_images`, `ImageBudget`), granted in the order
  of its slides (so the same seed generates for the same slides, in parallel or not), estimates their cost by list
  price before it generates any, keeps to `TALKGENERATOR_IMAGE_COST_LIMIT` if it's set, and its deck's usage counts
  them (`images`, `image_cost_usd`, `failed_images`), apart from its language model requests. Generated pictures are
  credited "AI-generated with <model>", in the `generated` license class (the provider's terms in the deck), shown in
  a browser from the app's own copy (`display: copy`, as Pixabay's), and kept on disk by model, prompt, shape and
  seed (`generated-images/` in the cache folder), so a talk made again, or a deck rendered again, generates nothing
  again. Talkgenerator's own rules come before the provider's moderation (`talkgenerator.images.safety`): a prompt
  that names a real person, the talk's presenter, a brand or a trademarked character, or asks for gore or sexual
  content, is never sent, every prompt asks for none of that, and a talk whose topic a slide shouldn't make light of
  generates nothing; a refused or failed picture keeps its stock photo.
- **New image sources** (milestone 5, docs/v5-plan.md 10.4), each with its license classes, its display policy and
  its filters: **The Met** (public domain artworks, CC0; its search since October 2026, v1.1, and an object per
  request), the **Cleveland Museum of Art** (CC0), the **Wellcome Collection** (medicine, science and odd history:
  public domain and CC BY, asked for by license), the **Smithsonian** (CC0; needs a free api.data.gov key,
  `DATA_GOV_API_KEY`), **NASA's Image and Video Library** (public domain, leaving out pictures it notes as
  someone else's; NASA's take on almost anything: pizza aboard the space station), **Flagpedia's flags** (public
  domain, by a country's name) and **Imgflip's meme templates** (fair use, for the memes above). None but the
  Smithsonian needs a key, and every one loads in a browser from its own server (display `direct`). The museums
  take one filter vocabulary in a look's source parameters: a type (painting, photograph, print, drawing,
  sculpture) and the years after and before which it was made, which the Art Institute of Chicago's search now
  takes too. They joined the looks they fit: `museum` (all the museums), `vintage` (old photographs from the Met,
  the Art Institute, Cleveland and the Smithsonian), `old-photo`, `portrait` and `old-people` (the museums'
  portraits), `space-science` (NASA first, and the Smithsonian's Air and Space Museum), `illustration` (Wellcome's prints and drawings) and `weird-stock` (now and then
  NASA's or Wellcome's odd pictures, for the `ted` format's punchlines); and two new looks, `meme-templates` and
  `country` (where the presenter comes from: its flag now and then, else photos of it). Their search answers are
  cached for 7 to 30 days.

### New kinds of slides

- Fourteen kinds drawn as texts on shapes, so that they need no image source (but for a post's and a headline's
  photo): a **big number** with what it counts and a made-up source, **KPI tiles**, a **quiz** (the answer on a
  click), a **social media post**, a **news headline**, an **agenda**, a **section** divider, **Questions?**, and
  native diagrams: a **timeline**, a **pyramid**, a **funnel**, a **cycle**, a small **org chart** and an **iceberg**,
  with their punchlines on a click. They come out the classic way too, in every theme and in the 2019 template, and
  a talk has at most one of each.
- **Venn diagrams** and **2×2 matrices**, with the punchline where the circles overlap or as one named dot, on a
  click.
- Two new charts: a **trend** (a line along two odd axes, going one of eleven ways, from exponential to hockey stick
  to crash, with an optional second line that wipes in as the punchline, and a named moment on the line) and a
  **ranking** (bars that the last one wins by far). Charts with axes get axis titles, and charts come labelled in
  funny ways, or bare, for the presenter to explain.
- **Memes with live captions** (a `meme` slide, docs/v5-plan.md sections 8 and 10.4): one of 25 well-known
  templates of Imgflip's (Drake Hotline Bling, Two Buttons, Distracted Boyfriend, Gru's Plan, Expanding Brain...),
  with its captions as texts on the picture, each in the box the template has for it (`data/memes.json`, measured
  on Imgflip's pictures): white Impact in capitals with a black outline, or plain black text on the template's own
  white or pale area (Drake's panels, Gru's boards). The talk's dice pick the template, and the language model
  writes what each box says, knowing what it's for (Drake waves the first away and points at the second); a
  classic talk takes each template's own sentences about the slide's topic and the words related to it, speaking
  of it as English does ("Love penguins", "Love coffee", "Is this a lighthouse?": the `generic` and `one` template
  functions, by wordfreq's frequencies of a noun and its plural). Gru's fourth board repeats his third, and the Bell
  Curve's wise one says what its simple one said. A deck holds
  a meme as a picture, texts and shapes, which every renderer draws already (talk-generator-web without changes);
  its picture keeps its look in every theme (no treatment moves its captions). Memes weigh four times what the
  other slides in the middle of a talk do: about half of all 10-slide talks have one, and a talk has two at most,
  from its third slide on, and only where its license policy allows fair use (not in `ted`).
  `talkgenerator formats --memes` lists the templates and what each caption says, for plans
  written elsewhere, whose `template_query` names one; a picture whose boxes talkgenerator doesn't know gets its
  captions at its top and its bottom. A caption too long for a narrow box (a sign's) gets a box grown around it,
  within the picture. A talk's two memes never share a template.
- Five kinds from real PowerPoint karaoke and battle decks, TED parodies and bad-PowerPoint humour (docs/v5-plan.md,
  section 8), drawn as texts on shapes in every theme and in the 2019 template, classic and by the language model:
  a **fun fact** ("Did you know?" or "Fun fact" in the talk's language, on a sticker over the fact, with a made-up
  source and a photo, or on a sticky note); an **acronym** for a made-up method (the S.P.A.R.K. method), its letters
  on tiles with their words, the last one, the punchline, on a click; a **dare** for the presenter ("Challenge":
  present the next slide as a haiku), on a card or between bands of warning tape; a **flowchart** whose Yes and No
  lead to the same end, which appears on a click; and a **tier list** from S to F, its S tier on a click. A talk has
  at most one of each, in its middle; a dare is rarer, as organisers put one such slide in a deck at most.
- A real chart from the internet (Reddit's) now comes under a confident conclusion that it supposedly proves, two
  times in three, or bare, as karaoke decks have them.

### Classic texts: the TED content pack

- Classic talks take their texts from the TED content pack (`talkgenerator/data/packs/ted`, docs/v5-plan.md section
  11): a grammar per kind of slide, and a manifest with the pack's version and the slots the code fills in, with
  their variables and length limits (`talkgenerator.sources.packs`). It has every classic text of TED-like talks, the
  memes' classic captions too, and about three times as many as before (2,870 templates, from 909, besides the lists
  of jobs and countries): titles in a TED talk's voice ("The Quiet Revolution of Penguins", "Notes From a Penguin
  Survivor"), about-me slides, history, statements, captions, charts, diagrams, big numbers and KPI tiles, quizzes,
  posts and headlines, agendas and sections, the karaoke types, memes and conclusions. Every template speaks of the
  topic as English does, keeps to its slide's length with long words, and is checked by `tests/test_content_pack.py`.
  Jobs a family audience doesn't need (escort, embalmer, soldier...) left the presenters' list.

### Titles and presenter names

- What someone types can be the topic or the title (`--topic_or_title`, `topic_or_title=`): "penguins" as well as
  "Why I Joined a Penguin Cult". What's clearly a title (four words or more, or a question or exclamation) stays the
  title, with its obvious slips fixed; anything shorter is the topic, or a premise ("Cats are liquid"), on which the
  language model builds a funnier, more specific title; in quote marks, it's the title, word for word. Misspelled
  topics are fixed ("pengiuns": "penguins"), but in a talk in another language, typed words of that language
  stay as typed ("matare", not "mature"), and so do compounds of Dutch, German and Swedish words ("tomatbok"); the
  deck says how what was typed was read.
- Made-up presenter names in styles (`--name_styles`): `pun` ("Prof. Anna Tomy" for medicine), `fun_surname`
  ("Linda Hivesworth" for bees) and `famous_pun` ("Albert Einstone" for geology) by default, and `classic`, the
  random first and last name of 2019. The language model writes the name in the same request, and a name that won't
  do (too long, a placeholder, a real famous name, one on a short blocklist) is turned down. Without a model,
  talkgenerator has names of its own for 642 of the 736 topics in its topic list. A plan can name its presenter
  (`presenter_name`).

### Personas

- Every talk has a presenter persona, which its seed picks: a disgraced professor, a startup founder, a medieval
  historian, a conspiracy blogger, a kindergarten teacher and eight more (`--persona`, `persona=`, the MCP server's
  `generate_talk`; `talkgenerator.personas.catalog()` lists them). The persona is more than the voice the language
  model writes in and the kind of talk they give. With a model or without, it shapes the talk:
  - the kinds of slides it favours: a historian's timelines and history, a founder's KPI tiles and funnels, a
    teacher's quizzes. No kind of slide is left out, and the format's caps still hold;
  - its title: the persona's kind of title from the model, and half of a classic talk's titles from the persona's
    own templates ("Disrupting Penguins");
  - the presenter's name: a historian's is a famous-name pun more often, and a professor goes by "Prof.", unless
    `--name_styles` says which styles to use; and with a model, the presenter's job ("Founder and CEO of
    Penguin.ly");
  - the theme, when it's random: the persona's favourite families come up 3 to 4.5 times as often (a kindergarten
    teacher's `kids` and `chalkboard`, a conspiracy blogger's `hacker terminal` and `newspaper`), and across all
    personas every family about as often as before;
  - the pictures: favourite looks for some of the looks slides ask for, searched first (a historian's weird
    pictures are weird medieval art, a founder's photos office stock), with the slide's own look after them.
- The deck and `talk.started` say which persona a talk had (`persona`: its name, label and voice, and the angle the
  model was given). `--persona none` makes the format's own talk.

### Talks that stream, and decks

- Every talk is a deck (`talkgenerator.models.deck`): plain, versioned JSON data with every text, image, credit and
  layout, which the PowerPoint is drawn from, so the two always match. `--save_json true` saves it next to the
  PowerPoint, `slide_deck.to_deck()` returns it, and `talkgenerator.render.powerpoint.render_pptx` draws a saved deck
  again.
- `generator.stream_talk()` hands a talk over while it's made: `talk.started` once its title is known, a
  `slide.ready` for every slide, in order and laid out in its theme, and `talk.finished` with the whole deck, the same
  deck as a talk made at once. A language model's slides come while it writes the rest, and images are probed rather
  than downloaded, as a browser loads them itself. talkgenerator.com streams its talks this way, and
  `image_util.forget_downloads()` gives back the memory of a PowerPoint's downloaded images, for a server.
- A deck's images say how a browser may show them (`display`: `direct`, `proxy`, `copy` or `local`, as their sources'
  terms allow), their size, their license and their look, and a streamed slide tells Unsplash that its photos were
  used, as a PowerPoint does. What appears on a click is marked on its element (`appears_on_click`), for renderers
  that play clicks.
- `slide.updated` (`talkgenerator.models.events.SlideUpdated`): in a talk that streams, a slide handed over before
  comes again, at its index and laid out as before (`DeckLayout.again`), once a generated picture takes its stock
  photo's place; `talk.finished` comes once every picture is in.

### Checks

- `talkgenerator check` makes talks on a set of topics (10 by default, `--quick` for 3, `--all` for 30, `--random N`
  from talkgenerator's list of 736 topics), checks every deck (every slide has what it needs, no template leftovers
  such as `{seed}`, images credited and allowed by the license policy, the talk's language, and in themed talks texts
  whose letters read on what's behind them, a theme's decoration and background pattern included, that fit their
  boxes and stay on the slide), makes every talk again with its seed to see
  that it comes out the same, and writes a JSON report. `--llm` checks talks a language model writes (the second run
  replays its answers), `--theme` themed talks, and `--decks` saves every deck. `talkgenerator.topics` has the list
  of topics, for suggestions.

### Changed

- A talk's look is a theme its seed picks (`--theme random`), not the 2019 template: `--theme classic` or
  `TALKGENERATOR_THEME=classic` keeps the template.
- A classic talk on a topic talkgenerator has presenter names for gets one of them, instead of a random first and
  last name: `--name_styles classic` keeps the random ones.
- A classic talk's mix of slides and its title depend on its persona: `--persona none` keeps the format's own.
- A seed gives another talk than in 4.x: every slide draws from its own random streams of the talk's seed now
  (`talkgenerator.util.random_util`), and the new kinds of slides (about one in six of a talk's slides) and names come
  into it. A talk without a seed gets a random one, which the logs and the deck mention, so any talk can be made
  again.
- Images come through the image finder, from about the same sources with about the same weights as before. History
  slides show old photographs in black and white or sepia, statements' backdrops come from Pixabay, Unsplash and
  Pexels (they were Pixabay's only), Reddit's chart slides take charts from r/dataisugly too, and Reddit's images say
  what they show. Searching sources a few at a time asks more of them per image.
- Charts are quieter, so that the joke stands out: no gridlines, tick marks or numbers along their axes. A yes/no
  chart's columns have their shares on top, a doughnut its shares on its ring and a legend, and chart texts are
  bigger, in the template's or the theme's font.
- GIPHY's searches aren't cached any more, as GIPHY's API rules forbid it; the other search APIs still are.
- `SlideDeck.to_slide_deck_dictionary()` returns the deck's slides, which are JSON, instead of dictionaries holding
  image and chart objects: a breaking change for code that read those (see Deprecated).
- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old names
  still work).
- New dependency: pydantic. New extras: `openai`, `anthropic`, `llm` and `mcp`.
- The README is shorter, and `docs/` has pages on the command line, language models, keys and settings, images and
  themes, using it with Claude and from Python, and migrating from 4.x.
- A deck's `usage` counts its generated pictures too (`images`, `image_cost_usd`, `unpriced_images`,
  `failed_images`, apart from `requests`, which stay its language model's), and the talk's log line says what they
  cost. A deck's `language_model` is the language model that answered, never an image generator.
- The credits of generated pictures name their model, not a license (`licenses.SHOWN` is open and public domain
  licenses only); `talkgenerator formats --details` (and the Skill's slide references) say which images prefer a
  generated picture.
- With the new image sources, a seed's talk finds other pictures than before: history slides take old photographs
  from the Met, the Art Institute and Cleveland too, an about-me slide's "where I come from" picture is now and
  then the country's flag, and the flavour packs search more subreddits (each checked for pictures among its hot
  posts on 2026-11-07): `cursed` r/TIHI and r/Cursed_Images, `wholesome` r/rarepuppers and r/Eyebleach,
  `bad-charts` r/Infographics and r/MapsWithoutNZ, `accidental-art` r/accidentalart and r/PerfectTiming,
  `pareidolia` r/facesinthings, `old-photos` r/OldPhotosInRealLife, `memes` r/HistoryMemes and r/ProgrammerHumor,
  `weird` r/Weird and r/notinteresting.
- The design check of an outlined text (WordArt's, a meme's) judges it per colour that may be behind it: white with
  a black outline reads on black by its white and on white by its black.

### Deprecated

- `generator.generate_presentation()` keeps working throughout talkgenerator 5, with a `DeprecationWarning` that
  points to `generator.stream_talk()` (whose `talk.finished` event has the deck, which `render_pptx` turns into a
  PowerPoint) or to `talkgenerator.plan.external.render_plan()`. talkgenerator's own commands, the MCP server and
  `stream_talk` don't warn.
- `SlideDeck.to_slide_deck_dictionary()` keeps working throughout talkgenerator 5, with a `DeprecationWarning` that
  points to `slide_deck.to_deck()`.

### Fixed

- Classic texts speak of the topic as English does: no more "How many the titanics are "too many the titanics"?",
  "Fanatic in Renewable A Plant That Won'T Die Systems", "Plant That Won'T Dies are great" or "Can we talk about
  regulator for a second?". The templates say `{seed.generic}`, `{seed.one}` and the new `{seed.bare}`, the thing
  after a word of the template's or before another noun ("The moon paradox" for "the moon", "a penguin expert" for
  "penguins"); title case leaves a word's other letters as they are ("Won't", "AI"); and `generic` speaks of time,
  work, art, science and life as amounts ("Hours with time", not "times"), and keeps a premise whole ("a plant that
  won't die"). A slide whose topic drifts to a word about the body (one went from "the Titanic" to "breasts") is
  made another way, as one about a faith or violence is.
- Classic memes read as English speaks of the topic: "Love coffee" and "Is this a lighthouse?", not "Love coffees",
  "happinesses" or "a the french revolution" (every caption pluralised the topic). The template functions
  `{seed.generic}`, `{seed.one}` and `.cap` tell a countable noun from a mass noun by wordfreq's frequencies of the
  noun and its plural.
- A text a language model wrote loses the backslash it put before a quote mark ("what\'s"), where its JSON needed
  none, and keeps the closing mark of a quote it ends on ("calling it 'Steve'" lost its last mark): only quote marks
  around all of a text go, and stray ones at its ends.
- `--int_seed` gives the same talk every time, also with `--parallel` (the default), with seed 0, and in every Python
  process: slides made in parallel shared one random generator, and seed 0 skipped the reseeding.
- No slide shows an image of a slide before it (nor nearly the same one). Conclusions, which may repeat texts as they
  sum up, could repeat a picture too, and a slide generator allowed to repeat a text could repeat an image, which
  generating in parallel then kept rejecting, round after round.
- Pictures shown whole keep their shape. They were padded by the wrong amount, so a 9:16 picture on a full-picture
  slide came out 43% too wide, and a square picture in an "About me" column 6% too narrow.
- Gif slides show gifs that move: their Reddit search takes only animated posts, an Imgur `.gifv` comes from Imgur
  instead of as Reddit's still of its first frame, and gifs of up to 16 MB are used (was 8). A file that's too large
  is turned down as soon as its host says how large it is.
- The texts on charts, such as a pie's names and shares, showed in black, whatever the chart's font said, so on the
  2019 template's black they didn't show at all; they're in the template's text colour now. Column charts no longer
  have gridlines, which v4 meant to leave out (but misspelt `has_mayor_gridlines`).
- WikiHow's search finds lists, quizzes and questions too, which became odd actions and titles ("e 20 Top Games Like
  Club Penguin"): only pages that teach an action count now.
- Template variables that share a start, like `{seed.plural}` and `{seed.plural.title}`, are filled in longest first:
  in an unlucky order, the longer one came out as garbage.
- Tracery grammars no longer keep growing in long-running processes such as the web app.
- The notes of chart slides no longer hold memory addresses, which made the same talk differ from one run to the
  next.
- Wikimedia Commons credits named some authors twice ("Unknown author Unknown author").
- Themed decks laid out on a computer without Verdana, Trebuchet MS, Arial Black, Impact or Comic Sans MS, as a
  Linux server or CI is, get the font sizes they get on Windows. Texts in those fonts were estimated from an
  average letter: up to twice as wide as they are, so they came out smaller than they had to, and in capitals or
  wide letters up to a quarter too narrow, so that a title in capitals could run out of its box, unseen by the
  design checks, which estimated the same way. talkgenerator now comes with every character's width in those fonts
  (`data/fonts/widths.json`, made by `scripts/font_widths.py`), and measures texts without kerning on every
  computer: Pillow kerns where it finds raqm, as on some Linux computers, so a text could get another size there.
- A Venn diagram's labels take long compounds too. When one of them doesn't fit its place in the circles even at 12
  points, as a 20-letter word didn't in three circles in any theme's font, all of them go beside the circles
  instead: left and right of them, and below the bottom one of three. The circles get smaller to make room, and
  the punchline keeps the middle, where it may spread over them. A diagram whose labels fit is drawn as before. In
  the classic template, a diagram's labels keep their words whole: PowerPoint broke a word wider than its line in
  two, as it did punchlines such as "Volcanoes" and "Lighthouses" at 32 points.
- A talk with an InspiroBot poster comes out the same every time its seed makes it. InspiroBot's API makes a new
  poster for every request, so `talkgenerator check` found that no such talk (about one classic talk in eight)
  came out the same in parallel and one by one. The poster is now drawn with the talk's seed from InspiroBot's
  older posters, at their predictable addresses (73 folders of 9,999 posters, from 2015 to 2017), which used to
  fill in when the API didn't answer. Talks without a seed get a random one, so they still get any of those
  posters, and no request goes to InspiroBot's API any more.
- `talkgenerator check` no longer finds a talk that came out differently because an answer of the on-disk cache
  expired between its two runs: Pixabay's expire after a day, and a fresh answer links the same pictures under other
  addresses, so a slide's picture changed its link. The second run now gets the answers the first one got
  (`http_util.same_answers`), as it gets a language model's; GIPHY's, which may not be kept, are still asked twice.
- The on-disk cache of API responses reads back what it keeps. Unsplash's searches, and Openverse's once it's
  signed in, were stored but never read back: their answers say they vary on `Authorization`, which the cache's keys
  leave out. And Pixabay's, Commons' and Openverse's, which say they vary on `Cookie`, stopped being read back once
  any host had set a cookie. Those searches went out again every time, using up rate limits (Unsplash's demo key
  allows 50 an hour). The cache no longer stores answers as varying on either header.
- A source that's skipped for a while, after an outage or a rate limit, still answers the searches it answered
  before, from its caches, and asks nothing new: before, it was skipped altogether. A cooldown that started in the
  middle of a talk, as Unsplash's demo key often makes one, lost the rest of the talk images that were found already,
  and made `talkgenerator check` find that a talk's second run came out differently. A source that's cooling down
  also keeps its place among a look's sources, so the sources searched together stay the same. That holds for
  Pixabay, Pexels, Unsplash, Openverse, Reddit and ConceptNet; GIPHY's answers aren't kept, so it finds nothing
  meanwhile, as before.
- A slide's key in the language model's answer never goes on a slide. A free model's conclusion called back to an
  earlier slide by its key: "Huddling scales trust (from slide_03)". The request now asks for callbacks by what the
  earlier slide said, never by its key or number; brackets that name a slide by its key are dropped from a text
  ("Huddling scales trust"), a key anywhere else in it makes the slide the classic generator's, as template code
  does, and `talkgenerator check` reports a key on a slide as an error.

## [4.0.1] - 2026-11-05

### Fixed

- The README now starts with `pip install talkgenerator`, and its links work on the
  PyPI project page.
- Corrected the 4.0.0 notes below: 4.0.0 is the first PyPI release since 2.1.4, and
  black was replaced by ruff rather than updated.

## [4.0.0] - 2026-11-05

The first release on [PyPI](https://pypi.org/project/talkgenerator/) since 2.1.4 in 2020
(`pip install talkgenerator`). This is the modernized, still pre-LLM version of the
generator described in the EvoMUSART 2019 paper: the same approach, brought up to date.

### Added

- New image and content sources: Openverse, Wikimedia Commons, the Art Institute of
  Chicago, GIPHY and Wikiquote. Image credits on the slides link back to the source.
- On-disk caching of search API responses (Datamuse, ConceptNet, Pixabay, Pexels,
  Unsplash), which keeps runs within each API's rate limits. Configurable with
  `TALKGENERATOR_CACHE_DIR` and `DISABLE_CACHE`.
- `.env.example`, and a `DISABLE_<SOURCE>` switch for every source.
- Unsplash photo credits (`Photo by <photographer> on Unsplash`), linking both the
  photographer and Unsplash as the API terms require.
- Gradual type checking with mypy, and a weekly "canary" workflow that runs the network
  tests against the live APIs and opens an issue when a source breaks.

### Changed

- Packaging moved to `pyproject.toml` and uv; CircleCI replaced by GitHub Actions.
- Publishing to PyPI through trusted publishing, so no API tokens are stored anywhere.
- Requires Python 3.11+ and Pillow 13 (which closes ~40 known vulnerabilities); the
  image formats the generator accepts are now restricted.
- Schema modules rewritten from star-imports into explicit registries.
- Openverse is used mostly as a fallback photo source, and is searched as a registered
  app when its credentials are set.
- The `ted` schema stays closer to the requested topic.
- Generation details are kept out of the speaker notes by default (`--debug_notes` to
  include them).

### Fixed

- Dead content sources and holes in generated decks.
- A slide whose images don't come through is now replaced by another slide, instead of
  leaving a hole.
- Reddit posts that link to Imgur now load the image from Reddit's own copy.
- ConceptNet failures fall back to Datamuse and WordNet instead of erroring.

### Dependencies

- All dependencies updated to current versions, now declared in `pyproject.toml` and
  locked in `uv.lock`; the old `requirements.txt` and `setup.py` are gone.
- black replaced by ruff for formatting and linting.

## [2.1.4] - 2020-03-26

The previous release on PyPI. Not covered in detail here.

## [Alpha] - 2019-08-06

Historical snapshot of the version accompanying the paper *"Automatically Generating
Engaging Presentation Slide Decks"* (Winters & Mathewson, EvoMUSART 2019). Preserved
as the `Alpha` git tag; it isn't on PyPI and isn't maintained for current Python.

[Unreleased]: https://github.com/twinters/talk-generator/compare/v4.0.1...HEAD
[4.0.1]: https://github.com/twinters/talk-generator/releases/tag/v4.0.1
[4.0.0]: https://github.com/twinters/talk-generator/compare/Alpha...v4.0.0
[2.1.4]: https://pypi.org/project/talkgenerator/2.1.4/
[Alpha]: https://github.com/twinters/talk-generator/tree/Alpha
