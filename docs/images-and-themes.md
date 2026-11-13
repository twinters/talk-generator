# Images and themes

## Images

Every image a slide asks for is a slot: what it's for, what to search for, its look, and the license classes it may
have. The image finder searches the look's sources a few at a time, in parallel, filters what they find (license,
size, orientation, descriptions that say NSFW, images the talk already has), takes a look at the thumbnails of a few,
and picks with the talk's seed: the same seed finds the same images, whichever search comes back first.

Credits on the slides link to the photographer's or the image's page, and name the license of openly licensed and
public domain images (such as "CC BY 2.0", linking to it). Stock photos are credited to their photographer and
platform, as the platforms ask. In a theme, the credits are small and quiet, in the bottom right corner: for whoever
wants to know where a picture came from, without drawing the eye from the slide. [Keys and settings](configuration.md#image-sources) lists the sources, and the keys
some of them need.

### Licenses

Every image has a license class:

| Class | What |
| --- | --- |
| `public-domain` | public domain and CC0 |
| `open` | Creative Commons BY and BY-SA |
| `stock` | the Unsplash, Pexels and Pixabay licenses |
| `generated` | AI images, under their provider's terms |
| `fair-use` | Reddit's posts, GIPHY's gifs, InspiroBot's posters and ShitpostBot's images |

A talk's license policy picks the classes its images may have: `all` (the default) every class, `open` everything but
fair use, for decks shown in public, or license classes separated by commas, such as `public-domain,open`. The `ted`
format keeps to `open` by default, and `--license_policy` (or `license_policy=` in Python) sets another policy for any
talk.

The search keeps to the policy, and slides whose images it allows no source for (memes and gifs under `open`, say)
aren't picked. The deck says every image's class and license, and `talkgenerator check` reports an image the policy
doesn't allow as an error. `talkgenerator formats --licenses` lists the policies.

### Looks

Every slot has a look (an aesthetic profile): the sources that have it, the filters that get it, and what to prefer
among the candidates.

| Look | Images |
| --- | --- |
| `photo` | stock photos, and Openverse's openly licensed ones |
| `calm-backdrop` | photos with little detail where a slide's big text goes, and not too light |
| `backdrop` | pictures behind a big number or KPI tiles, from many sources: stock photos most often, now and then a weird picture from Reddit, a NASA photograph, an old photograph or a painting |
| `product-shot` | photos of gadgets and inventions, for a made-up product (a pitch's, a keynote's) |
| `vintage` | old photographs in black and white or sepia |
| `museum` | public domain art from museums |
| `space-science` | space and science, as NASA and the like photograph it |
| `corporate-stock` | office stock photos in blues and teals |
| `illustration` | illustrations and drawings |
| `meme-chaos` | Reddit's weird pictures, ShitpostBot's images, gifs and memes |

Flavour packs are looks of weird content from curated sets of subreddits: `cursed`, `wholesome`, `bad-charts`,
`medieval`, `liminal`, `retro-futurism`, `accidental-art`, `pareidolia` and `corporate-cringe`, among others. Reddit's
NSFW mark and the finder's filters keep them safe for work. `talkgenerator formats --looks` lists every look, and
`talkgenerator formats --details` names the looks of every recipe's images.

A talk's persona (`--persona`) has favourite looks for some of the looks slides ask for, which are searched first: a
medieval historian's weird pictures are weird medieval art and their neutral photos museum art, a startup founder's
photos are office stock photos and their weird ones corporate cringe, a conspiracy blogger's weird pictures are faces
in things, a museum guide's are museum art and accidental Renaissance paintings, a nature-documentary narrator's are
landscapes and wholesome animals, and an alien anthropologist's weird ones are old photos of everyday human life. Where a favourite finds nothing, or the talk's license policy doesn't allow it, the slide's own look does.

The finder takes a look at its candidates' thumbnails: their brightness and colourfulness, how gray they are, how
much detail they have where the text goes, their main colours, and a perceptual hash that keeps nearly the same
picture from coming back on another slide. In a themed talk, pictures that go with the theme's colours come first,
and a vintage picture that isn't black and white or sepia turns sepia in a theme without a filter of its own.
`talkgenerator check` counts how many of every look's pictures have it.

Gifs move: Reddit's animated copies, and Imgur's. A gif too large to embed (many on r/gifs are 40 to 90 MB) plays as
Reddit's mp4 copy of it, which starts by itself and loops without sound, as the gif would.

### Generated pictures

In a talk a language model writes, an image generator can draw what stock photos can't show well: the presenter's
weird hobby, the cover of the book they wrote (with its title), an old photo of a moment in a made-up history, the
portrait of a made-up historical figure, a made-up news story's photo. The model writes a prompt for each, the slide
comes with a stock photo, and the generated picture takes its place once it's in (in a talk that streams, the slide
comes again, as `slide.updated`). A slide whose images can't be found at all gets a generated one on its last try,
too. Pictures are only generated when you ask for them, with your own key or server, never because a key is set:

| Generator | `--image_generator` | Key | Price a picture (list prices, checked 2026-11-07) |
| --- | --- | --- | --- |
| OpenAI | `openai` (gpt-image-2), or `openai:<model>` | `OPENAI_API_KEY` | $0.006 at low quality (`TALKGENERATOR_IMAGE_QUALITY` asks for `medium` or `high`) |
| [OpenRouter](https://openrouter.ai/)'s image models | `openrouter` (OpenAI's gpt-image-2 there), or `openrouter:<model>`, such as `openrouter:black-forest-labs/flux-3-image-klein` | the key that writes your talks | from $0.006 (none are free) |
| Google's Gemini (Nano Banana) | `gemini` (gemini-3.1-flash-lite-image), or `gemini:<model>` | `GEMINI_API_KEY` | $0.034 |
| Black Forest Labs' FLUX | `flux` (FLUX 3 Image Klein), or `flux:<model>`, such as `flux:flux-2-pro` | `BFL_API_KEY` | $0.009 |
| A ComfyUI server of your own | `comfyui`, or `comfyui:<checkpoint>` | none (`COMFYUI_URL`, `COMFYUI_WORKFLOW`) | nothing |
| An Automatic1111 (or Forge) server of your own | `automatic1111`, or `automatic1111:<checkpoint>` | none (`AUTOMATIC1111_URL`) | nothing |

`TALKGENERATOR_IMAGE_GENERATOR` sets one for every talk (`image_generator=` in Python), and
`DISABLE_IMAGE_GENERATION=1` switches them all off. A talk generates 3 pictures at most (`--generated_images`, or
`TALKGENERATOR_GENERATED_IMAGES`), estimates what they'll cost before it generates any (by list price:
`talkgenerator formats --generators` lists the models and their prices), and keeps to
`TALKGENERATOR_IMAGE_COST_LIMIT` (in dollars) if it's set; the logs and the deck JSON say what it spent.

Generated pictures are credited "AI-generated with <model>", in the `generated` license class (`--license_policy` can
leave them out), and kept in your cache folder, so making the talk again with the same seed, or rendering its deck
again, generates nothing again. A prompt that names a real person, a brand or a trademarked character, or asks for
gore or sexual content, is never sent (the stock photo stays), every prompt asks for none of that, and the generator's
moderation has its say too. Prices and default models are in `talkgenerator/data/image_generators.json`; an
`image_generators.json` in your config folder adds models or changes them, as image models come and go.

### The vision pick

The finder picks a picture by what its source says about it, and for some looks by a look at its colours, never by
what it shows. With `--vision_pick` (`vision_pick=` in Python), a vision model looks at the candidates instead, in a
talk a language model writes (or a plan): every picture of its slides keeps a few runners-up, the other candidates its
sources found, best first; once the last slide is made, one contact sheet shows every picture's candidates side by
side, up to four in a row (the finder's among them, in an order the talk's seed shuffles), and one request asks the
model what each row's candidates show and which one comes closest to what its slide asked for, or none. Its picks take
the finder's pictures' places once they pass the same checks; a row it turns down, a request that fails or takes over
30 seconds, and a budget that doesn't allow it keep the finder's pictures.

| `--vision_pick` | The model | What it costs |
| --- | --- | --- |
| alone, or `on` | the talk's own model when it reads pictures (Claude, OpenAI's models, Gemini), else OpenRouter's free models that do | as below |
| `openrouter` | OpenRouter's free models that read pictures: NVIDIA's Nemotron 3.5 Super VL, then dots-3 (`talkgenerator.images.vision.FREE_MODELS`) | nothing, but one request a talk of the free tier's 20 a minute and 1,000 a day (50 without $10 of credits), which the talks themselves use too: a talk takes two |
| `anthropic:claude-haiku-5-5`, `openai:<model>`, ... | that model, on your own key | Claude Haiku 5.5: about $0.001 a talk, by list price (a sheet of ten rows is about 1,500 tokens) |
| `none` | off (the default) | |

It's one request a talk, however many pictures it has (the first ten), never with the presenter's name, in the
talk's budget and its ledger (`usage.vision_requests` in the deck). In a talk that streams, the slides come with the
finder's pictures as they would without it, and a slide whose picture the model changed comes again (`slide.updated`)
once it has answered, before `talk.finished`. The deck says what the model made of every picture it saw (an image's
`vision`: `picked`, `kept` or `refused`) and which model it was (`vision_model`); `talkgenerator check --vision_pick`
counts them, and replays the answers when it makes a talk again. Classic talks have no vision pick, and neither do gifs,
InspiroBot's posters, meme templates and flags.

Measured on 2026-11-08 with the free models, on 12 talks: the request took 3 to 11 seconds, `talk.finished` came 9 to
24 seconds after the last slide in talks streamed live, and the pictures that show what they were searched for went
from 36% to 50% of those the model saw (judged by eye). The free models still turn a row down now and then where a
candidate would have done; the finder's picture stays then.

## Themes

`--theme` picks a talk's look: by default `random`, a theme the talk's seed picks, and `classic` for the 2019
template. Every other theme draws the slides as shapes on a 1920×1080 canvas: a layout puts every text and picture in
its box, and every text gets the largest size at which it fits.

The themes come in families: `clean keynote`, `dark minimal`, `corporate`, `academic`, `startup`, `vintage paper`,
`kids`, `brutalist`, `neon`, `hacker terminal`, `blueprint`, `chalkboard`, `newspaper`, `Swiss poster`, `sticky
notes`, `90s desktop`, `corkboard`, `spreadsheet`, `Y2K`, `70s retro` and `glossy magazine`, and, for laughs, `1997
WordArt`, `Comic Sans everywhere` and `clip-art corporate`. A family has many members, and the talk's
seed picks one: its colours (every text reads on its background, by WCAG's contrast rules), its fonts, its
decoration and its layouts.

- `--theme random` picks a family too, the ones for laughs included unless `--no_extreme_themes` leaves them out,
  and the talk's persona (`--persona`) favours some: a kindergarten teacher's talks are in `kids` or `chalkboard`
  about half the time, a conspiracy blogger's in `hacker terminal` or `newspaper`, a startup founder's in `startup`
  or `Swiss poster`.
- `--theme_families "dark minimal,Swiss poster"` keeps a random theme to some families (and with `--theme chaos`,
  every slide's): a talk whose seed picks one of them keeps its theme, and the others get one of them, the persona's
  favourites still weighting them.
- `--theme chaos` gives every slide a theme of its own, and `--style_chaos 0.3` does that for about a third of them.
- `TALKGENERATOR_THEME` sets the look of talks that don't ask for one, such as `classic` to keep the 2019 template.
- A plan can have a `theme` too, which `talkgenerator render --theme` overrides.

Every family has a decoration of its own, on every slide, and saves its big pieces for the title and section slides:

- `hacker terminal`: green or amber phosphor on black in a monospace font, a terminal window's title bar, scanlines,
  a prompt before the titles and a block cursor after the talk's title, pictures in windows of their own, and a
  status line with the slide's number.
- `blueprint`: white lines on a blueprint's blue grid, a border with registration marks, a dimension line under
  every title, pictures as figure plates, a title block with the slide's number, and a red pencil's punchlines.
- `chalkboard`: chalk on a green or slate board in a wooden frame, with chalk and an eraser on its ledge, eraser
  strokes, dashed chalk underlines, doodles, and pictures taped on.
- `newspaper`: newsprint, a masthead's rules with the edition's numbers, a front page for the title slide, rules
  between columns, red kickers and grayscale photos.
- `Swiss poster`: a grotesk flush left on a three-column grid, a heavy black rule, one red block a slide, a big red
  circle on the title slide and black section dividers with a giant number.
- `kids`: a kindergarten's, in bright colours on pastel paper, as one of four sets of decoration (the seed picks
  which, and every set is in its member's colours): crayon drawings (bunting along the top, crayon squiggles under the
  titles, confetti, a title card with a sun, a cloud and hills, section numbers on a sun), a sticker book (titles on
  white labels, stickers, pictures as stickers peeling off, a rainbow, section numbers on a prize rosette), a school
  notebook (ruled or squared paper with a margin line and a binding, ballpoint doodles, pictures taped in, an
  exercise book's cover for the title slide) or paper cut-outs (construction paper with small shadows, pictures on
  paper mats, paper hills and a paper flower).
- `sticky notes`: a workshop on a whiteboard, in its aluminium frame with markers on its tray: marker strokes under
  the titles, sticky notes with ideas scribbled on them (and dot-vote stickers, on the big slides), pictures held up
  by magnets, and the slide's number on a sticky flag.
- `90s desktop`: every slide a bevelled grey window with a title bar and its three buttons, a taskbar with the
  slide's number in its tray, pictures in windows of their own, and a big slide of nothing but texts as a dialog box
  on the desktop, with icons and the mouse's pointer.
- `corkboard`: cork in a wooden frame, the title on a pinned index card, pictures as polaroids, pinned or taped up,
  index cards pinned in free corners, and on the big slides pins with a red string between them.
- `spreadsheet`: a grid of cells with its columns' letters and its rows' numbers, the title a selected cell,
  pictures with selection handles, and the slide's number on the open sheet's tab, in Calibri.
- `Y2K`: chrome headings on pastel gradients, sparkles and glossy bubbles, pictures in white rounded frames, a CD on
  the big slides, and the slide's number on a glossy pill.
- `70s retro`: browns, oranges and mustard on cream (or avocado, or brown), four rounded stripes turning the top
  left corner, a sunset of stripes on the big slides, and pictures as prints with round corners.
- `glossy magazine`: big serif headlines, hairline rules and a page's folio, giant quotation marks by a quote,
  pictures on a block of colour, and an issue's roundel on the big slides.
- The others too: academic's titles on a band with a row of dots counting the slides (as LaTeX's Beamer has them),
  neon's sunset over a grid floor, vintage paper's ornamented double frame, brutalist's titles on blocks with hard
  shadows, corporate's slanted panel, startup's soft blobs, Comic Sans' speech balloons and POW, WordArt's
  starbursts, clip-art's swoosh, and keynote's and dark minimal's quieter marks and slide numbers.

The decoration never sits behind a text's letters unless the text is made to read on it, and its own texts (a slide's
number, a prompt) are numbers, symbols and code, so they suit a talk in any language.

Every slide type has its layouts, and a slide never gets the layout of the slide before it when another one fits;
some families have title and section slides of their own. Pictures get their theme's treatment, so that pictures
from mixed sources share one look. Most stay as they are, or get a gentle tint: a slight warm or cool cast, a wash of
the theme's paper or its accent. The strong filters are for the families made for them, and only for the photos
behind a slide's texts, where a picture matters little (a statement's, a big number's): grayscale in newspapers and
Swiss posters, sepia on vintage paper, a duotone in a terminal's green, a cyanotype's blue or neon's colours (black
and white goes grey there); every other picture keeps its colours, so that funny pictures don't all look the same.
A title slide shows a photo of the talk's world beside its title (its format's, a wedding toast's wedding, or its
persona's), and a section divider and a dare now and then stand over a picture of what they're about. Frames, grain
and a vignette come with some families, and some frame pictures
their own way (a terminal's window, a sticker's border, tape). PowerPoint applies filters as picture effects, so the
deck keeps the original picture ("Reset Picture" brings it back). Some families' headings get WordArt-style effects
(1997 WordArt's rainbow, bent into a wave or an arch; neon's glow; brutalist's hard shadow), drawn as text effects,
so the text stays text.

Themes use fonts that nearly every computer has, such as Arial, Calibri, Georgia, Impact and Comic Sans MS.
talkgenerator measures texts with open fonts of the same widths (Liberation, Carlito, Caladea and Gelasio, which come
with it), so a deck lays out the same on a computer without the originals. Every family but the three for laughs also has
two pairings of open fonts with more personality, from Google Fonts, which a theme picks two times in three. They
come with talkgenerator and travel inside every .pptx that uses them, and each has a stand-in that nearly every
computer has, at a size at which the texts fit in either.

Slides animate as the 2019 template's do: two or three columns appear click by click, the one before dimming, a
picture's frame with it. A slide of a list of things (figures, a quiz's options, levels, steps, an org chart's people,
a tier list's tiers, a ranking's bars from the top down...) shows its things one by one, a click each, the
punchline last, and a diagram's punchline appears on a click. By the slide's number, a small ring for every click
fills on its click, so the presenter sees at a glance whether the next click brings more of the slide or the next
one. A renderer that plays no clicks shows it all from the start;
`talkgenerator.render.preview.steps_sheet(deck)` draws a deck's slides click by click.

`talkgenerator check --theme random` checks themed talks, and also that their texts read on their backgrounds, fit
their boxes and stay on the slide. For a settings menu, `talkgenerator.design.themes.catalog()` lists every theme with
a label, a line on what it looks like, and whether it's one of those for laughs.
