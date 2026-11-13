# The slides of a `documentary` talk

A nature documentary about the topic as a wild species, in a hushed voice: the opening shot, its habitat, its behaviour, a rare sighting, its rituals, the dangers it faces and a closing reflection, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format documentary`.

A plan's `title` is like a nature documentary's title or episode: grand, hushed and a little dramatic, in a few words, and its `presenter_job` is their part in the documentary, as its credits would put it: its narrator, its wildlife camera operator or its field researcher.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `opening` | 1 | `opening-line-documentary`, `opening-shot-documentary` |
| `habitat` | 1 | `habitat-fact-documentary`, `natural-habitat-documentary`, `where-it-is-found-documentary` |
| `behaviour` | 1 to 2 | `a-day-in-the-life-documentary`, `behaviour-documentary`, `side-by-side-documentary` |
| `sighting` | 1 | `rare-sighting-documentary`, `sighting-in-the-news-documentary` |
| `ritual` | 1 | `ancient-ritual-documentary`, `courtship-dance-documentary` |
| `threat` | 1 | `danger-documentary`, `fewer-every-year-documentary`, `left-in-the-wild-documentary` |
| `closing` | 1 | `closing-reflection-documentary`, `farewell-documentary`, `stay-very-still-documentary` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `natural-habitat-documentary` | The species' natural habitat, in one photo, under a title that names it: a grand one, or an absurdly everyday one | the default; `title`: the species' natural habitat, as the narrator names it, in a few words; images: `image` places, else photo; tags: habitat, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `opening-shot-documentary` | The documentary's opening shot: a sweeping landscape of the species' world, filling the slide, under the narrator's hushed first line | the default; `title`: the narrator's first line, in a few words, as the narrator would whisper them; images: `image` places, else photo; tags: full_image, opening |
| `rare-sighting-documentary` | A rare sighting: an odd photo of the species, filling the slide, as the crew's first footage of it | `title`: what the narrator says about it, in a few words, as the narrator would whisper them; images: `image` weird-stock; tags: full_image, sighting |
| `ancient-ritual-documentary` | The species' ancient ritual, in an odd photo filling the slide, under the narrator's line about it | `title`: the narrator's line about the ritual, in a few words, as the narrator would whisper them; images: `image` weird-stock; tags: full_image, ritual |
| `farewell-documentary` | The documentary's last shot: the species at sunset, filling the slide, under the narrator's farewell, or what next time's episode is about | `title`: the narrator's farewell, or next time's episode, in a few words, as the narrator would whisper them; images: `image` photo; tags: closing, full_image |
| `full-screen-neutral-images-documentary` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `full-screen-gif-documentary` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `provocation-documentary` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a nature documentary's narrator whispers them, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 90 | the big text over the photo: one short sentence |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `opening-line-documentary` | The documentary's opening, over a calm photo: a grand, hushed line that introduces the topic as a wild species | the default; `text`: the narrator's opening line, in one or two short sentences, grand and hushed; images: `background` calm-backdrop or backdrop; tags: opening, statement |
| `danger-documentary` | The danger the species faces, over a photo: something harmless and everyday, told as a grave threat | `text`: the danger, as the narrator tells it, in one or two short sentences; images: `background` calm-backdrop or backdrop; tags: statement, threat |
| `closing-reflection-documentary` | The narrator's closing reflection on the species, over a calm photo, as the documentary ends | `text`: the narrator's last reflection, in one or two short sentences, hushed and a bit too deep; images: `background` calm-backdrop or backdrop; tags: closing, statement |
| `full-screen-pixabay-deep-documentary` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |

## `two_columns`

Two captioned images side by side.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |
| `caption_1` | 40 | the left caption |
| `caption_2` | 40 | the right caption |

Images: `image_1`, `image_2`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `side-by-side-documentary` | The species in two photos side by side: two stages of its life, or two of its moods, the second the punchline | the default; `title`: the slide's title, as a nature documentary's caption has it: a few words; `caption_1`: the first stage or mood, in one to three words; `caption_2`: the second, the punchline, in one to three words; images: `image_1` photo, `image_2` photo; tags: behaviour, two_captions |

## `three_columns`

Three captioned images side by side.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |
| `caption_1` | 40 | the left caption |
| `caption_2` | 40 | the middle caption |
| `caption_3` | 40 | the right caption |

Images: `image_1`, `image_2`, `image_3`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `behaviour-documentary` | Three photos of the species' behaviour, each with what it's doing, the last one what it's really doing, the punchline | the default; `title`: the slide's title, as a nature documentary's caption has it: a few words; `caption_1`: what it's doing, in one to three words; `caption_2`: something else it does, in one to three words; `caption_3`: what it's really doing, the punchline, in a few words; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: behaviour, three_captions |

## `history_quote`

A made-up historical figure's portrait, next to their quote.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | a title about history |
| `name` | 50 | a made-up historical figure (never a real person): their name, a comma, and their title |
| `quote` | 100 | what this made-up figure once said, in one short sentence |

Images: `portrait`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `historical-figure-quote-crf` | What a made-up historical figure once said about the slide's concept | the default; images: `portrait` portrait (or generated, from its prompt, with an image generator set up); tags: history, quote |

## `chart_categories`

A pie chart of made-up shares.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 60 | the question the pie chart answers, as its title |
| `categories` | 80 | two to five short answers, separated by \| |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `where-it-is-found-documentary` | Where the species is found, as a pie chart of its habitats, the wild ones and the absurdly everyday ones | the default; `question`: the chart's title: where the species is found; `categories`: three or four habitats, separated by \|; tags: chart, habitat, pie_chart |

## `chart_trend`

A line chart of a made-up trend along two odd axes; a second line, if any, draws itself across it on a click, as the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the chart's claim, as its title, in a few words: what it shows, such as a headline would say it, never 'X vs Y' (the two things it compares go on its axes) |
| `x_axis` | 40 | what the chart goes along, such as 'Hours since the meeting started' (or empty, for none) |
| `y_axis` | 40 | what the line measures, such as 'Times someone said synergy' (or empty, for none) |
| `shape` | 20 | how the line goes: `rising`, `falling`, `exponential`, `diminishing`, `hockey stick`, `peak`, `crash`, `plateau`, `rollercoaster`, `dip`, `flat` (or empty, for any) |
| `line` | 30 | the line's name in the legend, such as 'Me' (or empty, for none) |
| `second_line` | 30 | a second line's name in the legend, such as 'My cat'; it appears on a click, as the punchline (or empty, for none) |
| `second_shape` | 20 | how the second line goes: `rising`, `falling`, `exponential`, `diminishing`, `hockey stick`, `peak`, `crash`, `plateau`, `rollercoaster`, `dip`, `flat` (or empty, for any) |
| `event` | 40 | a moment on the first line, marked where it takes off, turns or drops, such as 'I got a cat' (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fewer-every-year-documentary` | The species' numbers over the years, falling, with the moment it all went wrong: something harmless and everyday arriving, told as a disaster | the default; `title`: the chart's claim about the species' numbers; `shape`: how the line goes: falling, or crash; `line`: the species; `event`: the moment it all went wrong, marked on the line; shows no `second_line`; shows no `second_shape`; tags: chart, threat, trend_chart |

## `big_number`

A big, made-up number, with what it counts under it: a figure the presenter has to explain; over a picture of what it's about, or beside it, if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |
| `number` | 12 | the big number, with its unit if it has one: a percentage, an amount or a count |
| `label` | 50 | what the number counts or measures, in a few words |
| `source` | 60 | a made-up, unreliable source for the number (or empty, for none) |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `left-in-the-wild-documentary` | How few of the species are left in the wild, as one big number | the default; `title`: the slide's title, as a nature documentary's caption has it: a few words; `number`: how many are left: a small number; `label`: what it counts, without the number itself; `source`: a made-up, unreliable source for the count; images: `background` backdrop; tags: big_number, threat |

## `quiz`

A quiz question for the audience, with three or four options (A to D), which appear one by one, a click each; the answer, and why, appear on the click after them.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 70 | the quiz question, in one short sentence |
| `option_a` | 36 | option A (without its letter), in a few words |
| `option_b` | 36 | option B |
| `option_c` | 36 | option C |
| `option_d` | 36 | option D (or empty, for none) |
| `answer` | 1 | the letter of the right option: `A`, `B`, `C`, `D` |
| `explanation` | 60 | why that's the answer, shown with it, in a few words (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `spot-the-species-documentary` | A quiz for the audience about the species: which of some ordinary things is really it, what it eats, how long it sleeps, or what sound it makes | the default; `question`: the quiz question, about the species; `explanation`: why that's the answer, as the narrator would whisper it; tags: quiz |

## `news_headline`

A made-up news story with a photo, as breaking news on television or on a newspaper's front page.

| Text | At most | What to write |
| --- | --- | --- |
| `outlet` | 30 | the made-up name of the newspaper or the channel |
| `headline` | 70 | the headline |
| `subheadline` | 70 | a line under the headline, with more of the story (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `sighting-in-the-news-documentary` | The news of a rare sighting of the species, as a nature paper reports it, with its photo | the default; `outlet`: the made-up name of a nature paper or channel; `headline`: the headline: the sighting, as big news; `subheadline`: a line under it: what an expert or a witness says; images: `photo` weird-stock; tags: news, sighting |

## `cycle`

A cycle of three to five steps around a circle, each leading to the next, and the last back to the first; they appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the cycle's title |
| `step_1` | 24 | the first step |
| `step_2` | 24 | the second step |
| `step_3` | 24 | the third step |
| `step_4` | 24 | a fourth step (or empty, for none) |
| `step_5` | 24 | a fifth step (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `a-day-in-the-life-documentary` | A day in the life of the species, as a cycle: three to five things it does, the last leading back to the first | the default; `title`: the slide's title, as a nature documentary's caption has it: a few words; `step_1`: a thing it does, in one to three words; `step_2`: a thing it does, in one to three words; `step_3`: a thing it does, in one to three words; `step_4`: a thing it does, in one to three words; `step_5`: a thing it does, in one to three words; tags: behaviour, cycle |

## `process`

A process of three to five steps, each leading to the next by an arrow, from the first to the last, the punchline; they appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the process's title |
| `step_1` | 40 | the first step |
| `step_2` | 40 | the second step |
| `step_3` | 40 | the third step (the last, the punchline, if there are no more) |
| `step_4` | 40 | a fourth step (or empty, for none) |
| `step_5` | 40 | a fifth step (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `courtship-dance-documentary` | The species' courtship dance, or the ritual by which it greets another, step by step, the last step the punchline; for all ages | the default; `title`: the slide's title, as a nature documentary's caption has it: a few words; `step_1`: a step of the dance, in two to five words; `step_2`: a step of the dance, in two to five words; `step_3`: a step of the dance, in two to five words; `step_4`: a step of the dance, in two to five words; `step_5`: a step of the dance, in two to five words; tags: process, ritual |

## `meme`

A meme: a well-known template's picture, with its captions in the template's boxes. Its template_query names the template, one of those `talkgenerator formats --memes` lists (with what each caption says), such as 'Drake Hotline Bling'. Two captions or more appear one by one, a click each, the last one the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `text_1` | 70 | the meme's first caption |
| `text_2` | 70 | its second caption (or empty, for none) |
| `text_3` | 70 | its third caption (or empty, for none) |
| `text_4` | 70 | its fourth caption (or empty, for none) |

Images: `template`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `meme-documentary` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 100 | the fact: one short sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `habitat-fact-documentary` | A fact about how the species lives in the wild, stated with total certainty, with its photo | the default; `fact`: the fact: one sentence about how the species lives, stated as certain; `source`: a made-up source: the crew's notes, a ranger, a survey; images: `photo` photo; tags: fun_fact, habitat |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 90 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 90 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `stay-very-still-documentary` | The documentary's last moment, as audience participation: the narrator hushes the whole room, as if the species were right there and might be scared off | the default; `audience`: what everyone in the room does, whispered to them: keep very still and quiet, for the species is close; shows no `dare`; tags: closing, dare |
