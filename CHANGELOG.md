# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

The start of talkgenerator 5 (see [docs/v5-plan.md](docs/v5-plan.md)).

### Added

- License classes and policies (`talkgenerator.images.licenses`): every image source declares the license classes
  of its images (`LICENSES`, next to its `DISPLAY`): `public-domain`, `open` (CC BY and BY-SA), `stock`
  (Unsplash, Pexels and Pixabay), `generated` and `fair-use` (Reddit, GIPHY, InspiroBot, ShitpostBot); Openverse's
  and Wikimedia Commons' images each have their own, and Openverse is only asked for CC0, the public domain mark,
  CC BY and CC BY-SA. A talk's license policy (`--license_policy`, `license_policy=` in `generate_presentation`,
  `stream_talk`, `render_plan`, the MCP server's tools and `talkgenerator check`) picks the classes it allows:
  `open` everything but fair use, `all` (the default) every class, or the classes, as `public-domain,open`. The
  `ted` format keeps to `open` by default. The image search keeps to it, slides whose images it allows no source
  for aren't picked, images and decks say their class, license and license link (`ImageData.license`,
  `ImageAsset.license_class`, `Deck.license_policy`), credits name open and public domain licenses ("CC BY 2.0",
  linking its deed), and `talkgenerator check` reports an image the policy doesn't allow as an error, and a credit
  that doesn't name its license as a warning. `talkgenerator formats --licenses` lists the policies.
- Image slots and the image finder (`talkgenerator.images.slots`, `.finder`): every image a slide asks for is a
  slot (`ImageSlot`: its intent, queries, orientation, fewest pixels, where its text goes, its look, license classes
  and sources) instead of a call to a source, and v4's image generators are slots too, under their old names.
  The finder searches a look's sources a few at once, in parallel (with v4's caches and cooldowns), filters what
  they find (license, size and orientation as the sources tell them, unsafe descriptions, the same image twice,
  the slide's own images), scores a few by a look at their thumbnails, checks the winner as before (a probe while
  streaming, a download otherwise) and picks with the talk's seed: the same seed finds the same images, whichever
  search comes back first. v4's weighted mixes of sources became the looks' source weights. A recipe (or one of
  its variants) can leave a slot out: its builder gets None for it, and the language model writes no query for it.
- Aesthetic profiles (`talkgenerator.images.profiles`): named looks, with their sources, the sources' own filters
  (Unsplash's and Pexels' colours and orientations, Pixabay's colours, image types and orientations, Openverse's
  categories and collections, Wikimedia Commons' categories), query modifiers, preferences and a treatment:
  `photo`, `neutral`, `calm-backdrop`, `vintage`, `museum`, `space-science`, `corporate-stock`, `illustration`,
  `meme-chaos` and more, attached to the slide types (history pictures are `vintage`, statements' backdrops
  `calm-backdrop`, ...), and a format can have looks of its own. A look whose sources can't or don't find anything
  hands over to its fallback. Flavour packs, looks of weird content from curated subreddits: `cursed`,
  `wholesome`, `bad-charts` (Reddit chart slides), `medieval`, `liminal`, `retro-futurism`, `accidental-art`,
  `pareidolia`, `corporate-cringe`, and v4's sets of subreddits. `talkgenerator formats --looks` lists them, and
  the formats' slide references name each recipe's image looks.
- A look at images (`talkgenerator.images.analysis`), with Pillow, on thumbnails: brightness, colourfulness, the
  share without colour, whether a picture is monochrome (black and white, or toned such as sepia), detail where a
  slide's text goes, main colours, and a perceptual hash. A vintage slot prefers black and white and sepia, a calm
  backdrop little detail where its text goes, and a themed talk pictures that go with its theme's colours; a
  vintage picture in colour turns sepia in a theme without a filter of its own. Decks keep what the look found
  (`ImageAsset.analysis`, and `look`), nearly the same picture doesn't come back on another slide, and
  `talkgenerator check` warns about pictures without their look's preference (a vintage picture in colour) and
  about near-duplicates, and counts per look how many pictures have it.
- The deck format: a generated talk as plain, versioned JSON data (`talkgenerator.models.deck`), which the
  PowerPoint renderer (`talkgenerator.render.powerpoint`) draws. `--save_json` (or `save_json=True`) saves it
  next to the PowerPoint, `slide_deck.to_deck()` returns it, and a saved deck renders again on its own.
- `talkgenerator.llm`, the groundwork for LLM-written talks: one interface for every language model provider; a
  `replay` provider that records answers on a cassette and replays them, for offline tests and for making a
  recorded talk again; a ledger of every talk's requests, tokens and cost; budgets (a $0 budget lets only free
  models through); and list prices. `TALKGENERATOR_LLM` picks the provider, and a deck tells what its talk asked
  of language models.
- Talks a language model writes: Python still picks every slide's generator, and the model writes what goes on
  those slides, in one streamed request whose JSON schema is made for the talk (its title, the presenter's job,
  its thesis, then every slide in order), so slides get ready while the answer comes in. A slide that comes out
  wrong, whose images can't be found, or that repeats what came before, is classic; so is the whole talk when
  the model fails or turns the topic down. The presenter's name never reaches the model, and the same seed with
  the same answers gives the same talk. `--llm provider:model` (or `llm=`, or `TALKGENERATOR_LLM`) picks the
  model, `--language` the language it writes in, and `budget=` what it may cost. Every slide generator has a
  recipe (`talkgenerator.plan.kinds`) that tells the model what to write for it; the plans it writes
  (`talkgenerator.models.plan`) are the format that talks written elsewhere, such as by a Claude Skill, will use
  too.
- Language model providers, with their SDKs as optional extras (`talkgenerator[openai]`,
  `talkgenerator[anthropic]`, or `talkgenerator[llm]` for both):
  - `openrouter`: OpenRouter's free models (its free router by default), with your `OPENROUTER_API_KEY`. They
    write talks whenever there's a key, at no cost, and without thinking first, which takes a talk from minutes
    to seconds (models that have to think do so as little as they can). Models listed after the first
    (`openrouter:<model>,<fallback>`) are fallbacks, and only providers that hold to the talk's schema get the
    request.
  - The prompt tells the model what each field of each slide is for, and that a slide's seed word is a starting
    point, not its title: the free models didn't read that from the schema alone.
  - `anthropic`: Claude, Claude Opus 5.5 by default, with your `ANTHROPIC_API_KEY`: structured outputs, thinking
    at low effort (`TALKGENERATOR_LLM_EFFORT` changes it), and server-side fallbacks when a request is declined.
  - `openai:<model>`: OpenAI's models through the Responses API, with your `OPENAI_API_KEY`.

  Paid models only write talks when `--llm` or `TALKGENERATOR_LLM` names them. A talk that a model declines,
  even halfway, is classic. Budgets check every model a request may end up at, and leave room for thinking. Keys
  never show up in logs or error messages.
- `talkgenerator render plan.json` turns a talk plan written elsewhere (by Claude through the Skill, by hand, ...)
  into a PowerPoint, with the deck's JSON (`<name>.deck.json`) and a contact sheet of its images
  (`<name>.images.png`) next to it, and prints a report in JSON: per slide, whether it came out as planned, was
  made the classic way instead, or was left out, and why, what every image was searched with and where it's from,
  and warnings about texts that were cut off and fields that don't exist. A slide's recipe (one of the format's slide generators, such as `two-captions-gifs`)
  picks its look and image sources, and an image query may name an image file of the user's own.
  `talkgenerator formats --details` lists the slide kinds, their texts, limits and recipes, and
  `talkgenerator schema plan` prints the plan format as a JSON Schema.
- The talkgenerator Skill (`skill/`): Claude writes talks for PowerPoint karaoke and improvised TED talks, renders
  them with `talkgenerator render`, and fixes them from the report. It installs as a Claude Code plugin straight
  from this repository (`/plugin marketplace add twinters/talk-generator`), or as a skill folder.
- `talkgenerator mcp`: a local MCP server, for Claude Desktop and other MCP clients (`pip install
  'talkgenerator[mcp]'`; the README says how to add it to Claude Desktop's config). The client starts it on the
  user's computer, over stdio, and it makes talks with the user's own keys and settings; nothing is hosted. Its tools:
  `list_formats` (the formats, themes and languages), `describe_format` (a format's slides, as `formats --details`),
  `get_plan_schema`, `render_plan` (a plan as a PowerPoint, with the report of `talkgenerator render`) and
  `generate_talk` (a talk on a topic, written by the language model the settings name, or else the classic way).
  They answer in JSON with the paths of the files they saved, save those only in the output folder
  (`--output_folder`, by default a `talkgenerator` folder in the user's documents) and never over another file, make
  one talk at a time, and tell the client every few seconds that a talk is still being made. A tool call can't pick
  the language model, so only the user's settings make a paid one write talks, and keys never show up in what the
  tools say or log. The Skill tells Claude Desktop users how to set it up. On Windows on Arm, the MCP SDK only
  installs in an x64 Python, as the `cryptography` package it needs has no wheels there.
- Talks in Dutch (`--language nl`), and in French, German, Spanish, Italian and Portuguese, when a language model
  or a plan writes them: talkgenerator's own words on the slides ("By ...", a chart's "Yes" and "No") are in the
  talk's language too, a slide that doesn't come out becomes a picture of its subject without text (the classic
  slides are English), and recipes that find English texts, such as real quotes, aren't used. A deck says its
  language, and a new check reads its texts with NLTK's stopword lists: a talk that reads as English when it
  shouldn't is an error, and such a slide a warning. `talkgenerator check --language nl --llm ...` checks them.
- Talks in Swedish (`--language sv`), as in the other languages: talkgenerator's own words are Swedish ("Av ...",
  "Ja" and "Nej", a post's "gilla-markeringar" and "delningar", a news story's "JUST NU"); without a language model,
  what's typed reads as a title when it starts like a Swedish one ("Varför", "Därför", "Så", "Hur") or makes a claim
  ("Katter är flytande"), but not for its "is", which is ice ("Pingviner på is"); and the language check doesn't
  count Swedish words that are English stopwords too ("in", "all", "just", "is") as English
  (`Language.english_lookalikes`). talkgenerator.com lists it among its languages once it runs a v5 with it.
- Themes (`--theme`, docs/v5-plan.md section 9): besides the 2019 template (`classic`), talks can be drawn as
  shapes on a 1920×1080 canvas, in a theme of one of twelve families, from `clean keynote` and
  `dark minimal` to `vintage paper` and `neon`, with `1997 WordArt`, `Comic Sans everywhere` and `clip-art
  corporate` for laughs. The talk's seed picks a member of the family: its colours (repaired until every text reads
  on its background, gradients included, by WCAG's contrast rules), font pair, casing, decoration and layouts.
  `--theme random` picks the family too (`--no_extreme_themes` leaves the extremes out), and it's the default:
  `TALKGENERATOR_THEME` sets another (`classic` keeps the 2019 template). `--theme chaos` gives every slide its own
  theme, and `--style_chaos` some of them. `generate_presentation(theme=...)` takes it per talk, and
  `talkgenerator.design.themes.catalog()` lists the themes with a label and a description, for a settings menu. A plan can have a `theme` too (or `talkgenerator render
  --theme`), which the Skill knows about. The layout engine (`talkgenerator.design.engine`) puts
  every element in its box and gives every text the largest size at which it fits, measured with the fonts' own
  files or fonts with the same metrics (`talkgenerator.design.fonts`; talkgenerator comes with the open ones: Liberation
  Sans, Serif and Mono, Carlito, Caladea and Gelasio, in `data/fonts`, so texts measure the same on a computer
  without Arial, Calibri and the rest), so a themed deck's JSON holds every
  element's place and style, and every renderer draws it the same way. `talkgenerator.render.shapes` draws it in
  PowerPoint, and `talkgenerator.render.preview` as pictures with Pillow, with a contact sheet of a whole deck.
  Every slide type has its layouts, twenty in all: a full-screen picture with its title on a band at the top or
  the bottom, or on a panel in a corner (and framed when it has no title), two pictures side by side with their
  captions under or above them, in zig-zag rows or on the two halves of the slide, a chart or picture beside its
  title, a statement centred, aligned left by a bar or on a band. A slide never gets the layout of the slide before
  it when another one fits, and less often the ones the deck has had already. Pictures, charts and diagrams go
  under the bands and texts over them. Slides animate as the 2019 template's do: two or three columns appear click
  by click (fading in), the one before dimming, and a video in a column starts playing as its column appears; a
  slide's reveals and videos add up, instead of the last taking the others' place.
  Pictures get their theme's treatment, so that pictures from mixed sources share one look
  (`talkgenerator.design.treatments`): grayscale, sepia, a duotone in the theme's colours, or black and white (split
  at the picture's own median lightness), rounded corners or a white polaroid frame tilted a few degrees, grain and
  a vignette. Vintage paper goes sepia with grain and polaroids, neon duotone, brutalist black and white, kids
  rounded and polaroid. PowerPoint applies the filters as picture effects, so the deck keeps the original picture
  (and "Reset Picture" brings it back), and previews apply them with Pillow.
  Headings get WordArt-style effects in some families: 1997 WordArt's rainbow in a black or white outline, with a
  drop shadow, bent into a wave, an arch, inflated or slanting up; neon's glow; brutalist's hard offset shadow;
  Comic Sans' light outline on a solid shadow; clip-art corporate's gradient with a soft shadow. PowerPoint draws
  them as text effects, so the text stays text (and editable), and previews with Pillow. A heading over a photo
  keeps its theme's text colour, and the design checks accept a text that reads by its outline.
- Design checks for themed decks (`talkgenerator.checks.design`): every text reads on what's behind it (a photo
  counts as black or white, as shaded), fits its box, isn't too small, stays on the slide and isn't covered by what's
  drawn after it, and no slide has the layout of the slide before it where another fits. On 2,376 themed decks made
  from 66 benchmark talks, nothing came up, nor on 792 decks of those talks laid out with twelve seeds. `talkgenerator
  check --theme random` checks themed talks, and its metrics count a deck's layouts and those twice in a row.
- Two new kinds of chart. A trend: a line along two odd axes ("Hours since the meeting started" against
  "Times someone said synergy"), going one of eleven ways, from exponential to hockey stick to crash, with an
  optional second line, the punchline, that draws itself across the chart on a click. And a ranking: bars that
  the last one, the punchline, wins by far. Both come out the classic way too, and a talk has at most one of
  each. A trend can also mark a moment on its line, where it takes off, turns or drops ("I got a cat"), and a
  correlation can have one outlier far above the others ("Me"): a big dot with its name. A field of a slide kind
  can be a choice (`TextField.options`, such as a trend's shape), which the language model picks from a list,
  and which the Skill's reference lists.
- Charts come labelled in funny ways, or bare, for the presenter to explain. A slide generator's recipe can have
  variants (`kinds.Variant`), which the talk's seed picks like the slides themselves: a language model writes
  a trend with funny axis titles and named lines, with axis titles only, or bare; a correlation with or without
  axis titles; a ranking with or without a title on its axis. Classic charts get axis titles from templates
  ("Hours spent thinking about cats", "Public opinion of naps"), and a third of them none. A trend's axes may
  stay empty in a plan too.
- Charts with axes get axis titles: the correlation curves now show the two things they correlate (v4 left
  them out), and a language model or a plan can name them (`x_axis` and `y_axis`). A deck's chart says its axis
  titles and whether its series appear one by one (`reveal`).
- Gifs too large to embed play as Reddit's mp4 copy of them: on r/gifs, many are 40 to 90 MB, while their mp4
  copies are mostly a few MB. In the slideshow, the video starts by itself and loops without sound, as the gif
  would, with a still of the gif as its poster frame. In a two- or three-column slide, whose columns appear one
  click at a time, a video appears with its column and starts playing then. A deck's image names the video in `video_url` (a renderer
  that plays no videos shows the still), and gifs of up to 16 MB stay gifs. A file that's too large is now turned
  down as soon as its host says how large it is, instead of after downloading up to 25 MB of it.
- Two new kinds of slide, drawn as PowerPoint shapes instead of images, so they need no image source: a Venn
  diagram, two or three see-through circles with a label each and the punchline where they overlap ("Things I
  love" and "Things that love me back": "Cheese"), and a 2×2 matrix, two axes with a title at each end, a label in
  each quadrant and one named dot as the punchline. The punchline appears on a click. Both come out the classic
  way too, from the words that ConceptNet (or Datamuse) relates to the slide's seed, and a talk has at most one of
  each. A deck holds them as diagram elements (`VennDiagram` and `MatrixDiagram` on a `diagram` slide), which the
  checks read for gaps and template leftovers. In a themed deck, a diagram goes under its title in the theme's
  colours and body font (`DiagramStyle`), with its circles or quadrants made lighter or darker until its labels
  read on them, and the design checks check that its labels read and fit.
- Fourteen more kinds of slide (milestone 6, docs/v5-plan.md section 8), drawn as texts on shapes, so they need no
  image source (but for a post's and a news story's photo) and every renderer draws them as it draws the others:
  - figures: a **big number** with what it counts and a made-up source ("97%" of lighthouses that have never seen
    a ship), and **KPI tiles**, three or four figures as on a dashboard, the last one the punchline;
  - a **quiz**: a question and three or four options, A to D; on a click, a band behind the right one, its letter
    on a stamp and an explanation;
  - mockups: a **social media post** (a made-up poster with their initials, handle, likes and shares, and a
    photo) and a **news headline**, as breaking news on television over its photo or on a newspaper's front page;
  - the talk's structure: an **agenda** after the title, a **section** divider in the middle, numbered by the deck
    (02, 03...), and **Questions?** as the last slide now and then;
  - native diagrams: a **timeline**, a **pyramid**, a **funnel**, a **cycle**, a small **org chart** and an
    **iceberg**, each with its punchline on a click where it has one (the last moment, the top, the bottom, the
    boss, what's under the water).

  Each is a kind for plans and the language model, with its field limits (`talkgenerator formats --details`),
  and comes out the classic way too, from templates (`data/text-templates/slide_texts.json`) and the words
  ConceptNet relates to the slide's seed, leaving out words on faiths, violence and hate, or not for a family
  audience. Each has two or three layouts in every theme, never the same twice in a row where another fits, and
  texts on tiles, badges and cards get colours that read on them. A classic deck draws them on the 2019
  template's blank slide, in the template's look (white Calibri on black, its orange and blue). A talk has at most
  one of each (sections: one per ten slides; diagrams, the Venn diagrams and matrices included: two in ten
  slides), from its third slide to the one before the conclusions, so the slide after the title still introduces
  the presenter: about 1.7 of a 10-slide talk's slides (2.2 in the `ted` format). Posts and news headlines say
  likes, shares and breaking news in the talk's language.
- A deck's texts, pictures and shapes can appear on a click of their slide (`appears_on_click`), as a quiz's
  answer and a KPI slide's last figure do: PowerPoint fades them in on that click, and a renderer that plays no
  clicks shows them from the start (talk-generator-web needs a change to hold them back in its presentations).
- `talkgenerator login openrouter`: sign in to OpenRouter in the browser (OAuth with PKCE), and talkgenerator gets
  a key of its own, which it keeps in the user's config folder (readable only by the user), so OpenRouter's free
  models write talks without an `OPENROUTER_API_KEY`. `--headless` signs in on a computer without a browser,
  `--status` says how many free requests are left today, and `talkgenerator logout openrouter` forgets the key.
- `generator.stream_talk()`: a talk handed over while it's made, as events (`talkgenerator.models.events`):
  `talk.started` (title, presenter, language, theme tokens), a `slide.ready` for every slide in order, laid out
  in the talk's theme, and `talk.finished` with the whole deck, which is the same as `generate_presentation`
  makes. Slides are settled as soon as they can be: a language model's while it still writes the rest, and
  classic slides made in parallel each once its work is done. Leaving the loop stops the talk, also while it
  waits for the model, whose answer then isn't read any further. For talkgenerator.com's view of talks that
  stream in (docs/v5-plan.md, section 13.1). Its images are probed rather than downloaded (`image_util.probing`):
  their first bytes tell their format and size, so a check reads 64 KB instead of the whole file, which a
  browser loads itself. Images that don't tell their size early, and those shaped like a known "image not
  available" placeholder, are still downloaded whole, and a gif too large to embed probes its video copy. On 33
  images of earlier talks, probes took 9.7 s against 43.8 s for downloading them. `image_util.forget_downloads()`
  empties the cache of downloaded images (up to 96 MB), for a server once it has made a PowerPoint: on
  talkgenerator.com's 450 MB, two downloads in a row otherwise took the service to its memory cap.
- A deck's images say how a browser may show them (`display`), as their sources' terms and servers allow:
  `direct` from their links (Unsplash and GIPHY require it; Wikimedia Commons, Pexels, Openverse's hosts, Reddit,
  InspiroBot and ShitpostBot load that way too), `proxy` through a pass-through proxy (the Art Institute of
  Chicago refuses requests without its `AIC-User-Agent` header), `copy` from the app's own copy or not at all (Pixabay doesn't
  allow hotlinking for good, and its links stop working after a day), or `local` (talkgenerator's own files).
  Every image source declares its policy (`DISPLAY`). A slide that streams tells its images' sources that they
  were used once it's handed over, as a PowerPoint does, so Unsplash counts the download. Images also say their
  size in pixels (`width` and `height`, the original's, probed or downloaded), so a browser can place a picture
  before it loads, and a deck (and `talk.started`) says which language model writes the talk (`language_model`:
  the one asked at the start, the one that answered in the deck; none for a classic talk).
- Presenter names in styles (`talkgenerator.names`): a talk without a presenter's name gets one made up in a style
  its seed picks among the switched-on ones (`name_styles=` on `generate_presentation` and `stream_talk`,
  `--name_styles`): `pun` ("Prof. Anna Tomy" for a talk on medicine), `fun_surname` ("Linda Hivesworth" for bees)
  and `famous_pun` ("Albert Einstone" for geology; never a real name as it is, nor a living person's or a
  dictator's) by default, and `classic`, the random first and last name of 2019. The language model that writes
  the talk writes the name in the same request, in the talk's language and before the presenter's job, which
  agrees with it, after first writing what the name will play on (which isn't shown), and is shown two names of the
  style for other topics, with what they play on; a name that won't do (too long, template code, a placeholder, a
  name on a short blocklist, a famous name as it is, a copy of an example) is made up by talkgenerator instead. Talks without a language model get a name from talkgenerator's own pack
  (`data/text-templates/presenter_names.json`: 279 names by style and topic, drafted with a language model) when
  their topic is one it has names for, and a classic one otherwise, the same as before for the same seed. A given
  name still goes first and never reaches the model; `talk.started` and the deck carry the name the talk got.
  `names.catalog()` lists the styles for a settings menu, the MCP server's `generate_talk` takes `name_styles`
  (and `list_formats` lists them), and a plan can name its presenter (`presenter_name`), as the Skill now does.
- What's typed for a talk can be its topic or its title: `topic_or_title=` on `generate_presentation` and
  `stream_talk` (instead of `topic` and `title`), `--topic_or_title`, and the MCP server's
  `generate_talk(topic_or_title=...)`, for "penguins" as well as "Why I Joined a Penguin Cult". What's typed in
  quote marks is the title, word for word (talkgenerator.com has no other way to say so). What's clearly a
  title (four words or more, or a question or exclamation) stays the talk's title, with only its obvious slips fixed
  by the language model that writes the talk, in the same request ("waht my cat taught me about taxes": "What My
  Cat Taught Me About Taxes"); a title the model rewrites stays as typed, with the slips fixed that talkgenerator
  can fix itself (misspellings, a capital start). Anything shorter is the topic, or a premise, on which the model
  builds a funnier, more specific title ("Cats are liquid": "Cats Are Liquid: The Future of Fluid Startups"),
  spelled right; in English talks, the talk's seed picks whether up to three classic titles go with that, as titles
  to pick or as inspiration only, or none at all (the format's tracery titles and a wikiHow "How to ..." title, only
  those that mention the topic). Without a language model,
  talkgenerator guesses: a title also when it starts like one ("How to", "Why", "The", "A", "My", in the talk's
  language too) or makes a claim, which stays as typed. The topics are settled before the model is asked (a clear
  title's rarest word, or else what was typed), with misspellings fixed ("pengiuns": "penguins"). The deck and
  `talk.started` say how it was read (`topic_or_title`: the text, and `read_as` topic or title). A topic or a title
  given as such is taken as it is, with the same request as before (`talkgenerator.titles`).
- `talkgenerator login chatgpt`: Sign in with ChatGPT (OpenAI's sign-in for open-source apps that run locally, in
  preview), so that the models of your ChatGPT plan write your talks (`--llm chatgpt` or `chatgpt:<model>`, and the
  default once you've signed in), at no cost to talkgenerator: their requests count toward the plan's usage. The
  first sign-in registers talkgenerator with the account (OAuth with PKCE, back to 127.0.0.1), the ID token is
  checked against OpenAI's published keys, and the access token is refreshed as it runs out (one refresh at a
  time, also across processes). `--status` names the account and its models, `--new-account` switches accounts,
  and `talkgenerator logout chatgpt` ends the sign-in at OpenAI. A usage limit says where to manage it.
- A list of 736 topics for talks (`talkgenerator/data/topics.txt`, read with `talkgenerator.topics`), from cats
  and sourdough to "a printer that jams", inspired by the improv suggestion lists of Impy and
  improbotics-interface: for suggestions (talk-generator-web's random topic button keeps a copy) and for checks
  on varied topics, `talkgenerator check --random 20`, which draws the same topics for the same first seed.
- `talkgenerator check --decks <folder>` saves every talk's deck, to read what the talks say. The report counts
  the images that share a word with their search (of those whose source describes them) and the slides that
  repeat a title from before, and warns about a talk the language model wrote none of.
- `talkgenerator check --llm provider:model` checks talks a language model writes; to check that the same answers
  give the same talk, the second run replays what the first one got. The report says how many slides the model
  wrote.
- `talkgenerator check`: generates talks on a set of topics (10 by default, `--quick` for 3, `--all` for 30),
  checks every deck, generates every talk again one by one with its seed to see that it comes out the same, and
  writes a JSON report. The checks, in `talkgenerator.checks`: every slide has what its type needs, no template
  leftovers such as `{seed}` or `#symbol#` reach a slide, and images are credited and don't come back.

### Changed

- Images come through the image finder (see the image slots above): classic talks draw on the same sources with
  about the same weights as before, but history slides now show old photographs in black and white or sepia (by
  preference; no more r/ColorizedHistory or the Art Institute's paintings among them), statements' backdrops come from
  Pixabay, Unsplash and Pexels (they were Pixabay's only), Reddit's chart slides also take charts from
  r/dataisugly, and Reddit's images say what they show (their post's title). Searching sources at once asks more
  of them per image than before (two at a time, for most looks).
- Every slide is now drawn from its deck form, so a .pptx and its deck JSON always match. Slides look the same
  as before.
- `SlideDeck.to_slide_deck_dictionary()` returns the deck format's slides, which are JSON-ready, instead of
  dictionaries holding image and chart objects.
- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old
  names still work).
- Charts are quieter, so that the joke stands out: no gridlines, tick marks or numbers along their axes, which
  only showed made-up numbers. A yes/no chart's columns have their shares on top ("81%" over "Only on Tuesdays")
  instead of an axis of percentages; a doughnut has its slices' shares on its ring and a legend that names them;
  a correlation is round dots; a pie's slices are kept apart by thin lines; and in the classic template, a
  ranking's bars are grey but for the punchline, and a trend's second line comes in the punchline's red. Chart
  texts are bigger (18 to 24 points), in the template's or the theme's font, and axes are thin lines in a muted
  colour. A trend's named moment ("I got a cat") is on one line, beside its dot on the side the line leaves free.
- New dependency: pydantic. New optional dependencies: anthropic and openai (see the language model providers), and
  mcp (for `talkgenerator mcp`).
- With milestone 6's slide types in the mix, a seed's talk has other slides than it had before: about one in six
  of a talk's slides is one of them, and the other kinds come up a little less often.
- A talk without a seed gets a random one, which the logs and the deck JSON mention, so any talk can be made
  again.
- A classic talk on a topic that talkgenerator's pack of presenter names knows (642 of the 736 topics of
  `topics.txt`) gets a name from it, instead of a random first and last name: `--name_styles classic` keeps the
  random ones.
- Randomness comes from `talkgenerator.util.random_util`: every slide draws from its own streams of the talk's
  seed. A lint rule keeps the package from using the `random` module directly.
- GIPHY's searches aren't cached on disk any more, as GIPHY's API rules forbid caching its responses and media
  URLs (the other search APIs still are).

### Fixed

- A classic slide generator could show an image a slide before it had shown (when it was allowed to repeat
  something, such as a text), which generating in parallel then kept rejecting, round after round: now no slide
  repeats an image (nor nearly the same one), whichever way it's made.
- Wikimedia Commons credits named some authors twice ("Unknown author Unknown author").
- WikiHow's search finds lists, quizzes and questions too, which were cut into odd actions for classic slides and
  titles ("e 20 Top Games Like Club Penguin", "arn All About the 18 Different Penguin Species"): only pages that
  teach an action count now ("How to ...", "4 Easy Ways to ...").
- The spelling fixes of what's typed for a talk in another language than English no longer turn its words into
  English ones ("matare", Swedish for a feeder, became "mature"; Dutch "attractieve" became "attractive"), and in
  Dutch, German and Swedish, which write compounds as one word (`Language.compounds`), a word no language knows
  that's two of the language's words put together stays as typed, where it was taken for a near word ("tomatbok"
  became "tomato", "maanspion" "mansion", "Computerkrise" "computerised", "robotarmé" "robotar"). A word one edit
  from a known one is still fixed, and so is a Swedish word typed without its ring ("faglar": "fåglar", was
  "naglar"). On samples of typos of common words, as many are fixed as before in every language.
- In a themed deck, a title with a word too long for the column beside a picture or a chart, as Dutch and German
  compounds can be ("Vulkaanuitbarstingen"), goes across the top of the slide instead: in a wide font, such a word
  didn't fit the 600-pixel column even at the smallest size. Those layouts now take a title only if it has no word
  over 15 letters, as the side layouts of milestone 6's slide types do.
- Texts that a language model or a plan writes a little longer than their limit (by up to an eighth) stay whole,
  and a text that has to be cut no longer ends on a little word, as in "Cats were the true scholars of the" (in
  every language, with NLTK's stopword lists). The presenter's job may be 50 characters (was 40), and the prompt
  asks for the title and the job in the talk's language: the free models wrote them in English, after the
  English example. Gif slides no longer all get the teaser "Look at this", which the free models took from the
  prompt's example.
- A free model turned down a harmless topic (it said `safe_topic: false`), which made the talk classic. The flag
  now asks the other way around, as the plan had it: `unsafe_topic`, true only for a hateful or harmful topic.
  As another free model then turned down "penguins" that way, a talk a model finds unsafe is asked for once
  more, saying so; it's classic when the second answer finds it unsafe too.
- A talk that streams is the talk made at once also when the model writes its answer's properties in alphabetical
  order, as `dots-studio/dots-3-note-preview:free` does (OpenRouter's free router often picks it). Its title,
  thesis and unsafe flag came after the slides, so a streamed talk started with a classic title ("Never, Ever
  Make A Good Pot Of Coffee") where the same answer made at once got the model's, and took slides before the flag;
  and in a talk of 10 slides or more, `slide_10` came before `slide_2`, so a slide that wasn't in yet when its
  turn came was taken for skipped, and came out classic. The answer is in alphabetical order now too: the spine
  is one object, `about`, before the slides, whose numbers have as many digits as the last one's (`slide_02` to
  `slide_10`). And a streamed talk waits for all of the spine (or the end of the answer) instead of taking what
  there is of it once the first slide is in: as the spine comes first in either order, `talk.started` comes as
  early as before, and a model that writes the spine last, or its fields one by one, still gives a streamed talk
  all of it.
- When the model's provider fails before the model writes anything ("Provider timed out after 11796ms", which
  made one benchmark talk in thirty classic), OpenRouter gets the request once more; the free router may then
  send it to another model.
- The prompt no longer gives examples that the free models copied: half of the yes/no charts answered "Only on
  Tuesdays", every outlier was "Me" or "Finland", most conclusions were titled "Conclusions", and a third of the
  talks had an "Expectation vs Reality" slide.
- A ranking leaves out bars that are only numbers: a free model wrote its scores between the names ("Druids |
  6 | Priests | 4"), which made a number the winner.
- The texts that talkgenerator writes on charts itself, such as axis titles, a pie's names and shares, and a named
  point, show on every slide. PowerPoint drew them in black, whatever the chart's own font said, so on the classic
  template's black and on dark themes they didn't show at all. They're in the template's or the theme's text
  colour now, and a doughnut's shares in whatever reads on their slice.
- Column charts no longer have gridlines: v4 meant to leave them out, but misspelt them (`has_mayor_gridlines`).
- A doughnut in a theme named its slices twice: in a legend, and on its ring, where longer names ran into each
  other.
- No slide shows an image of a slide before it: conclusions, which may repeat texts as they sum up, could repeat
  a picture too.
- Gif slides show gifs that move. Their Reddit search takes only animated posts (gif subreddits hold photos
  too), an Imgur `.gifv` without Reddit's animated copy comes from Imgur itself instead of as Reddit's still of
  its first frame, and gifs of up to 16 MB (was 8) are used, as many good ones are 10 to 16 MB.
- `--int_seed` gives the same talk every time, also with `--parallel` (the default), with seed 0, and in every
  Python process. Slides generated in parallel are settled in order, so a talk comes out the same as when its
  slides are generated one by one.
- Template variables that share a start, like `{seed.plural}` and `{seed.plural.title}`, are filled in longest
  first: in an unlucky order, the longer one used to come out as garbage.
- Tracery grammars no longer keep growing in long-running processes such as the web app: every text gets a
  fresh grammar.
- The notes of chart slides no longer hold memory addresses (of their chart data and style), which made the
  same talk's deck differ from one run to the next. `talkgenerator check` found it.
- Pictures shown whole (`"fit": "contain"`) keep their shape. They were padded by the difference between their
  aspect ratio and their frame's, which only comes out right for a square picture in a frame wider than tall, or
  for a picture of its frame's own shape: on a full-picture slide, a 9:16 picture came out 43% too wide and a 4:3
  one 8% too narrow, and in the three columns of an "About me" slide, which are taller than wide, a square
  picture came out 6% too narrow. v4 drew them like that too.

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
