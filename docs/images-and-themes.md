# Images and themes

## Images

Every image a slide asks for is a slot: what it's for, what to search for, its look, and the license classes it may
have. The image finder searches the look's sources a few at a time, in parallel, filters what they find (license,
size, orientation, descriptions that say NSFW, images the talk already has), takes a look at the thumbnails of a few,
and picks with the talk's seed: the same seed finds the same images, whichever search comes back first.

Credits on the slides link to the photographer's or the image's page, and name the license of openly licensed and
public domain images (such as "CC BY 2.0", linking to it). Stock photos are credited to their photographer and
platform, as the platforms ask. [Keys and settings](configuration.md#image-sources) lists the sources, and the keys
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

## Themes

`--theme` picks a talk's look: by default `random`, a theme the talk's seed picks, and `classic` for the 2019
template. Every other theme draws the slides as shapes on a 1920×1080 canvas: a layout puts every text and picture in
its box, and every text gets the largest size at which it fits.

The themes come in families: `clean keynote`, `dark minimal`, `corporate`, `academic`, `startup`, `vintage paper`,
`kids`, `brutalist` and `neon`, and, for laughs, `1997 WordArt`, `Comic Sans everywhere` and `clip-art corporate`. A
family has many members, and the talk's seed picks one: its colours (every text reads on its background, by WCAG's
contrast rules), its fonts, its decoration and its layouts.

- `--theme random` picks a family too, the ones for laughs included unless `--no_extreme_themes` leaves them out.
- `--theme chaos` gives every slide a theme of its own, and `--style_chaos 0.3` does that for about a third of them.
- `TALKGENERATOR_THEME` sets the look of talks that don't ask for one, such as `classic` to keep the 2019 template.
- A plan can have a `theme` too, which `talkgenerator render --theme` overrides.

Every slide type has its layouts, and a slide never gets the layout of the slide before it when another one fits.
Pictures get their theme's treatment, so that pictures from mixed sources share one look: grayscale, sepia, a duotone
in the theme's colours, or black and white, rounded corners or a polaroid frame, grain and a vignette. PowerPoint
applies them as picture effects, so the deck keeps the original picture ("Reset Picture" brings it back). Some
families' headings get WordArt-style effects (1997 WordArt's rainbow, bent into a wave or an arch; neon's glow;
brutalist's hard shadow), drawn as text effects, so the text stays text.

Themes use fonts that nearly every computer has, such as Arial, Calibri, Georgia, Impact and Comic Sans MS.
talkgenerator measures texts with open fonts of the same widths (Liberation, Carlito, Caladea and Gelasio, which come
with it), so a deck lays out the same on a computer without the originals. Every family but the three for laughs also has
two pairings of open fonts with more personality, from Google Fonts, which a theme picks two times in three. They
come with talkgenerator and travel inside every .pptx that uses them, and each has a stand-in that nearly every
computer has, at a size at which the texts fit in either.

Slides animate as the 2019 template's do: two or three columns appear click by click, the one before dimming, and
what a slide holds back, such as a quiz's answer or a diagram's punchline, appears on a click. A renderer that plays
no clicks shows it all from the start.

`talkgenerator check --theme random` checks themed talks, and also that their texts read on their backgrounds, fit
their boxes and stay on the slide. For a settings menu, `talkgenerator.design.themes.catalog()` lists every theme with
a label, a line on what it looks like, and whether it's one of those for laughs.
