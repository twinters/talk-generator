# The command line

`talkgenerator` makes a talk. Its subcommands turn talks planned elsewhere into PowerPoints, check talks, sign in to
language model providers, and serve talkgenerator to Claude Desktop and other MCP clients.

| Command | What it does |
| --- | --- |
| `talkgenerator --topic peanuts` | Makes a talk, saves it as a PowerPoint in `output/`, and opens it |
| `talkgenerator render plan.json` | Turns a talk plan into a PowerPoint, and reports in JSON on how it came out |
| `talkgenerator formats` | Lists the talk formats; with options, their slides, the image looks and the license policies |
| `talkgenerator schema plan` | Prints the plan format as a JSON Schema (`schema deck` for the deck format) |
| `talkgenerator check` | Makes talks on a set of topics, checks them, and writes a report |
| `talkgenerator login openrouter` | Signs in to OpenRouter, so that its free models write your talks (`login chatgpt`: your ChatGPT plan's) |
| `talkgenerator logout openrouter` | Forgets that sign-in (`logout chatgpt` ends the one with ChatGPT) |
| `talkgenerator mcp` | Serves talkgenerator's tools to Claude Desktop and other MCP clients, on your computer |

Every command takes `--help`.

## Making a talk

```sh
talkgenerator --topic peanuts --num_slides 10
```

This makes a talk of 10 slides, title slide included, saves it as `output/peanuts.pptx` and opens it. A file is never
overwritten: the next talk on peanuts becomes `peanuts_1.pptx`. The logs say what the talk is made of, which seed it
got, which sources had no keys, and, for a talk a language model wrote, how many requests it made and what they cost.

Who writes the talk depends on your settings: a language model when one is set up (see
[Language models](language-models.md)), and else the classic generator, the 2019 method of the
[paper](https://doi.org/10.1007/978-3-030-16667-0_9). `--llm none` always makes a classic talk.

### What the talk is about

| Option | What it does |
| --- | --- |
| `--topic` | What the talk is about. A common, well-known noun works best. Several topics, separated by commas, make one talk about all of them. Without a topic or a title, the topic is `cat` |
| `--title` | The talk's title. With only a title, its rarest word becomes the topic (just a topic is usually more fun) |
| `--topic_or_title` | Instead of `--topic` and `--title`: what someone typed, which could be either, such as `penguins` or `Why I Joined a Penguin Cult`. In quote marks, it's the title, word for word. Four words or more, or a question or an exclamation, is the talk's title, with only its obvious slips fixed. Anything shorter is the topic, or a premise (`Cats are liquid`), on which the language model builds a funnier, more specific title. Without a model, it's a title also when it starts like one ("How to", "Why", "The", "A", "My") or makes a claim, and stays as typed |
| `--num_slides`, `--slides` | How many slides, the title slide included (*default: 10*) |
| `--presenter` | The name on the title slide. It never goes to a language model. Without it, the talk makes one up (see `--name_styles`) |
| `--name_styles` | Without `--presenter`, the kinds of made-up names the talk's seed picks from, separated by commas: `pun` ("Prof. Anna Tomy" for a talk on medicine), `fun_surname` ("Linda Hivesworth" for bees), `famous_pun` ("Albert Einstone" for geology) and `classic` (a random first and last name, as in 2019). The language model writes the name; without one, talkgenerator has names of its own for many topics, and makes up a classic one for the others (*default: `pun,fun_surname,famous_pun`, as the talk's persona favours them*) |
| `--persona` | Who presents the talk: `disgraced_professor`, `startup_founder`, `medieval_historian`, `conspiracy_blogger`, `kindergarten_teacher`, `consultant`, `motivational_speaker`, `influencer`, `time_traveller`, `life_coach`, `retiree`, `former_athlete` or `passionate_expert`. They favour some kinds of slides (a founder's KPI tiles and funnels, a historian's timelines), give the talk their kind of title (half of a classic talk's titles are their own: "Disrupting Penguins"), nudge the style of the presenter's made-up name (unless `--name_styles` says), give the language model a voice and an angle, favour some theme families for a random theme (a teacher's `kids` and `chalkboard`), have favourite looks for some pictures (a historian's weird medieval art), and with `--schema random` favour some formats (a founder pitches). `none` makes the format's own talk (*default: `random`, a persona the talk's seed picks*) |
| `--personas` | The personas the talk's seed picks from, separated by commas, such as `startup_founder,consultant`. A talk whose seed picks one of them keeps it, and the others get one of them (*default: all of them*) |
| `--language` | The language of the slides: `en`, `nl`, `fr`, `de`, `es`, `it`, `pt` or `sv`. Other languages than English need a language model: a classic talk is English, and says so in the logs (*default: `en`*) |

### Who writes it

| Option | What it does |
| --- | --- |
| `--llm` | The language model that writes the talk, as `provider:model`: `openrouter` (OpenRouter's free models) or `openrouter:<model>[,<fallback>...]`, `anthropic` (Claude Opus 5.5) or `anthropic:<model>`, `openai:<model>`, `chatgpt` or `chatgpt:<model>` (your ChatGPT plan's models), and `none` for a classic talk (*default: `TALKGENERATOR_LLM`, or else your ChatGPT plan's models once you've signed in with ChatGPT, or else OpenRouter's free models when there's an OpenRouter key, or else `none`*) |

[Language models](language-models.md) says what each costs, and how to get the keys.

### Formats and license policies

`--schema` picks the talk's format: which kinds of slides it has, how often, and where its images may come from.
(`render` and `formats` call the same choice `--format`.) `random` leaves it to the talk's seed (see below).

| `--schema` | The talk | License policy |
| --- | --- | --- |
| `default` | A TED-like talk: about the presenter, history, bold statements, captioned images, charts, diagrams, quizzes and conclusions, with images from every source, memes and gifs too | `all` |
| `ted` | The TED-like talk with copyright-free images only (stock photos, artworks and old photos), for decks shown in public: no full-screen images, gifs or memes | `open` |
| `interview` | The TED-like talk, without slides about the presenter | `all` |
| `pitch` | A startup pitch to investors: the problem, the solution, the market (TAM, SAM and SOM), the business model, the traction, the competition, the team, the roadmap and the ask | `all` |
| `academic` | A talk at an academic conference, with affiliations on its title slide: the outline, related work, the method, the results (with p-values), the limitations, future work, the acknowledgements, the references and questions | `all` |
| `corporate` | A company's all-hands meeting or quarterly business review: the agenda, the KPIs against their targets, the quarter's wins, the roadmap, an org change, the synergies, the ask of everyone and Q&A | `all` |
| `keynote` | A product keynote on a big stage: a big opening statement, the one idea, the reveal of the product, its features, a live demo, the price, the "one more thing" and a closing line | `all` |
| `test` | For testing talkgenerator itself | `all` |

A pitch, an academic talk, an all-hands and a keynote go through the parts of their arc, in that order, whoever
presents them: a short talk keeps the parts that matter most (a five-slide pitch has the problem, the solution, the
traction and the ask; a five-slide keynote its opening, the reveal, a feature and the "one more thing"), and a long one
gives some parts more slides and has memes, quotes and the like between them. A startup founder pitches more often
than the other personas, a disgraced professor gives more of the academic talks, a management consultant more of the
all-hands and a startup founder or a motivational speaker more of the keynotes; their themes are the `startup`,
`academic`, `corporate` and `dark minimal` families more often. Their arcs' slides need no image that's fair use, so
`--license_policy open` keeps them whole. `talkgenerator formats --details --format pitch` lists a format's arc and the
slides of each part.

`--schema random` leaves the format to the talk's seed, which picks the persona first and then a format that persona
favours: in about half of their talks, a startup founder pitches, a disgraced professor gives an academic talk, a
management consultant an all-hands and a motivational speaker a keynote; most of the others give TED-like talks, in
6 to 8 of 10. Every format keeps a few talks in a hundred with every persona, and over all the personas almost 6 in
10 talks are TED-like. Only the formats for talks take part: `default`, `pitch`, `academic`, `corporate` and `keynote`. Copyright-free images go with any of them:
`--schema random --license_policy open`. The deck's `schema_name` says which format the talk got.

A format's license policy says which license classes its images may have. `--license_policy` sets another one:
`open` allows every image but fair use (no memes, gifs or Reddit's posts), `all` every image, and license classes
separated by commas pick those, such as `public-domain,open`. [Images and themes](images-and-themes.md#licenses)
lists the classes, and `talkgenerator formats --licenses` the policies.

`--list` lists the formats and the slide generators each one uses.

### What it looks like

| Option | What it does |
| --- | --- |
| `--theme` | `random` (a theme the talk's seed picks, of a family its persona favours more often), `classic` (the 2019 template), a theme family's name, such as `"dark minimal"` or `"1997 WordArt"`, or `chaos` (every slide in a theme of its own) (*default: `TALKGENERATOR_THEME`, or else `random`*) |
| `--style_chaos` | How many slides get a theme of their own, from 0 (none) to 1 (all) (*default: 0*) |
| `--no_extreme_themes` | Leaves the themes for laughs (1997 WordArt, Comic Sans everywhere, clip-art corporate) out of `--theme random` |
| `--theme_families` | The families a random theme can be of (and with `--theme chaos`, every slide's), separated by commas, such as `"dark minimal,Swiss poster"`: a talk whose seed picks one of them keeps its theme, and the others get one of them (*default: all of them*) |
| `--image_generator` | Generates pictures, at your own cost (see [Generated pictures](images-and-themes.md#generated-pictures)): `openai`, `openrouter`, `gemini`, `flux`, `comfyui` or `automatic1111`, each with `:<model>` if you like, or `none` (*default: `TALKGENERATOR_IMAGE_GENERATOR`'s, or else none*) |
| `--generated_images` | How many pictures a talk generates at most (*default: 3*) |
| `--vision_pick` | Has a vision model pick the pictures of the slides a language model writes, each among a few candidates it sees side by side, in one request a talk (see [The vision pick](images-and-themes.md#the-vision-pick)): alone or `on` for the talk's own model when it reads pictures, else OpenRouter's free models that do; or a model, such as `anthropic:claude-haiku-5-5`; or `none` (*default: none*) |

[Images and themes](images-and-themes.md#themes) describes the families.

### Seeds, files and logs

| Option | What it does |
| --- | --- |
| `--int_seed` | The seed for the talk's random choices: the same seed gives the same talk, with or without `--parallel`, as long as the sources (and the language model) answer the same. Without one, the talk gets a random seed, which the logs and the deck JSON mention |
| `--parallel` | Makes the slides at the same time, which is faster; the talk comes out the same either way (*default: true*) |
| `--output_folder` | Where the talks go (*default: `./output`*) |
| `--save_ppt` | Saves the PowerPoint (*default: true*) |
| `--open_ppt` | Opens the PowerPoint once it's saved (*default: true*) |
| `--save_json` | Also saves the talk's deck as JSON, next to the PowerPoint and with the same name, such as `peanuts.json`: the data the PowerPoint is drawn from (*default: false*) |
| `--debug_notes` | Explains in every slide's speaker notes how it was made. Off by default, as presenters see the notes |
| `--print_logs` | Prints what the generator does (*default: true*) |
| `--verbose`, `-v` | Prints the debug logs too |

`--parallel`, `--save_ppt`, `--open_ppt`, `--save_json` and `--print_logs` take `true` or `false` (or `yes` and `no`,
`1` and `0`), such as `--open_ppt false`.

## Rendering a plan: `talkgenerator render`

A plan is a talk written outside talkgenerator, by Claude through the [Skill](use-with-claude.md) or by you: what every slide
says, and what its images should show, as JSON. `render` finds the images, credits them, lays the deck out and saves
the PowerPoint:

```sh
talkgenerator render plans/birdwatching.json -o talks/birdwatching.pptx
```

Next to the PowerPoint go `birdwatching.deck.json` (the deck as data) and `birdwatching.images.png` (a contact sheet
of all its images). Then it prints a report in JSON: for every slide of the plan, whether it came out as planned, was
made the classic way instead, or was left out, and why; what every image was searched with, what it shows and where
it's from; the checks on the deck; and the sources it had to skip for lack of keys.

| Option | What it does |
| --- | --- |
| `plans` | One plan file or more; patterns such as `plans/*.json` work too, also on Windows |
| `-o`, `--output` | Where to save the PowerPoint (for one plan) |
| `--output_folder` | Where to save the PowerPoints, named after their plans (*default: `output`*) |
| `--presenter` | The presenter's name, before the plan's `presenter_name` |
| `--format` | The format, before the plan's own (*default: the plan's, or else `default`*) |
| `--theme` | The look, before the plan's own (*default: the plan's, or else `TALKGENERATOR_THEME`, or else `random`*) |
| `--license_policy` | The license classes the images may have (*default: the format's*) |
| `--image_generator`, `--generated_images` | Generated pictures, as for a talk (see [Generated pictures](images-and-themes.md#generated-pictures)) |
| `--vision_pick` | A vision model picks every image among a few candidates, as for a talk (alone or `on`: OpenRouter's free models that read pictures); the report says what it made of them |
| `--int_seed` | The seed for the random choices, such as which of the images found to use; the report gives the one it used |
| `--no_json`, `--no_contact_sheet` | Leaves out the deck's JSON, or the contact sheet |
| `--open` | Opens the PowerPoint afterwards |
| `--verbose`, `-v` | Shows the generator's logs, on stderr (the report goes to stdout) |

An image query may name an image file next to the plan, for a picture of your own. The command exits with 2 when a
plan can't be read or rendered (the report says why), and with 0 otherwise.

[An example plan](https://github.com/twinters/talk-generator/blob/master/skill/skills/talkgenerator/references/example-plan.json)
shows what goes in one.

## What a plan can hold: `talkgenerator formats` and `talkgenerator schema`

```sh
talkgenerator formats                          # the formats, with their license policies
talkgenerator formats --details --format ted   # the slides a plan for a format can have
talkgenerator formats --looks                  # the looks images can be found in
talkgenerator formats --licenses               # the license policies
talkgenerator schema plan                      # the plan format, as a JSON Schema
talkgenerator schema deck                      # the deck format, as a JSON Schema
```

`--details` lists every kind of slide a plan can have: its texts with their length limits, its images, and its
recipes (the slide generators that make it, each with its own look and image sources). `--json` gives any of these as
JSON instead of text, for programs.

## Checking talks: `talkgenerator check`

```sh
talkgenerator check --quick
```

`check` makes talks on a set of topics with the live sources, checks every deck, makes every talk again one by one
with its seed to see that it comes out the same, and writes a report to `output/check-report.json`. It exits with 1
when a talk has an error: a slide without what it needs, template code such as `{seed}` on a slide, an image its
license policy doesn't allow, a talk that comes out differently the second time, or, in another language than
English, a talk that reads as English. Warnings, such as a title with words of its request in it ("Come Up With
One: ..."), a credit that doesn't name its license, a quiz whose explanation names another option than its answer,
or a text about real-world politics in a talk that isn't about it, are in the report.

| Option | What it does |
| --- | --- |
| `--topics` | Topics, separated by commas (*default: a set of 10*) |
| `--quick`, `--all`, `--random N` | The first 3 topics of that set, all 30 topics, or N topics drawn from talkgenerator's list of 736 (the same N for the same first seed) |
| `--seeds` | Seeds, separated by commas (*default: 1*) |
| `--schema`, `--slides` | The format (or `random`, for one each talk's seed picks), and the slides per talk (*default: `default`, 10*); the report counts the formats and personas the talks got |
| `--persona`, `--personas` | As for a talk |
| `--llm` | The language model that writes the talks (*default: `none`, for classic talks*); the second run replays the first one's answers |
| `--language` | The language of the talks (other languages than English need `--llm`) |
| `--theme`, `--license_policy` | As for a talk; themed talks get the design checks too (texts that read on their backgrounds, fit their boxes and stay on the slide) |
| `--vision_pick` | As for a talk; the second run replays the vision model's answers too, and the report counts its picks |
| `--no_determinism` | Doesn't make every talk a second time |
| `--report` | Where to write the report |
| `--decks` | A folder to save every talk's deck in, as JSON, to read what the talks say |
| `--verbose`, `-v` | Shows the generator's logs |

## Signing in: `talkgenerator login` and `talkgenerator logout`

```sh
talkgenerator login openrouter            # OpenRouter's free models (the default)
talkgenerator login openrouter --status   # how many free requests are left today
talkgenerator login chatgpt               # your ChatGPT plan's models (Plus or Pro)
talkgenerator login chatgpt --status      # which account is signed in, and its models
talkgenerator logout chatgpt
```

`--headless` signs in to OpenRouter on a computer without a browser, and `--new-account` signs in with another
ChatGPT account than before. [Language models](language-models.md#signing-in) says what each sign-in does and
where talkgenerator keeps it.

## The MCP server: `talkgenerator mcp`

Claude Desktop and other MCP clients start `talkgenerator mcp` themselves, over stdio, on your computer: see
[Use it with Claude](use-with-claude.md#the-mcp-server) for how to add it. `--output_folder` is where it saves talks, and
nowhere else (*default: a `talkgenerator` folder in your documents*); `--verbose` logs debug messages too, on stderr.
It needs the MCP SDK: `pip install 'talkgenerator[mcp]'`. Run in a terminal, it says that it serves its tools, and
waits (Ctrl+C stops it).
