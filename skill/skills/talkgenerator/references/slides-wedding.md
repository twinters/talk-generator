# The slides of a `wedding` talk

A wedding toast by the best man or the maid of honour, for their best friend, who marries the topic: who the speaker is, how the couple met, an embarrassing story, why they're perfect together, marriage advice and the toast, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format wedding`.

A plan's `title` is like a wedding toast's title: the best friend and the topic as a couple, or a fond and embarrassing promise, in a few words, and its `presenter_job` is who they are to the couple, as a toast introduces them: best man, maid of honour, or a best friend since nursery school.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `intro` | 1 | `old-photo-wedding`, `then-and-now-wedding`, `who-am-i-wedding` |
| `how_they_met` | 1 to 2 | `happiness-since-wedding`, `love-story-wedding`, `the-day-they-met-wedding` |
| `story` | 1 to 2 | `red-flags-we-ignored-wedding`, `that-night-wedding`, `the-incident-wedding` |
| `couple` | 1 to 2 | `great-loves-wedding`, `perfect-match-wedding`, `side-by-side-wedding` |
| `advice` | 1 to 2 | `happy-marriage-pyramid-wedding`, `marriage-advice-wedding`, `marriage-is-like-wedding` |
| `toast` | 1 | `raise-your-glasses-wedding`, `the-toast-wedding`, `to-the-happy-couple-wedding` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `old-photo-wedding` | Who the speaker is: an old photo, under a title that says it's the speaker and the best friend, long ago (the speaker will explain whatever the photo shows) | the default; `title`: a title naming the speaker and the best friend, and the year or the occasion; images: `image` vintage, else old-photo, else photo; tags: intro, single_image |
| `the-day-they-met-wedding` | How the couple met: a photo of the topic, the day the best friend first saw it | `title`: a title about the moment the best friend met the topic, naming both; images: `image` photo; tags: how_they_met, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-incident-wedding` | An embarrassing story about the best friend: an odd photo, filling the slide, that the speaker has to tell the story of, under its name | the default; `title`: the story's name, as friends call it, such as the incident of a year or a place; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: full_image, story |
| `to-the-happy-couple-wedding` | The toast: a photo of the topic, filling the slide, under the toast to the happy couple | `title`: the toast to the happy couple, in a few words; images: `image` photo; tags: full_image, toast |
| `full-screen-gif-wedding` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `full-screen-neutral-images-wedding` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `provocation-wedding` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a wedding toast's speaker would say it to the room, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 90 | the big text over the photo: one short sentence |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `who-am-i-wedding` | Who the speaker is, over a photo: how they know the best friend, and a hint of what's coming | the default; `text`: the opening lines of the toast: one or two short sentences; images: `background` calm-backdrop or backdrop; tags: intro, statement |
| `marriage-is-like-wedding` | The speaker's wisdom on marriage, over a photo: what marriage is like, with the topic in it | `text`: one or two short sentences of wedding wisdom that go somewhere odd; images: `background` calm-backdrop or backdrop; tags: advice, statement |
| `the-toast-wedding` | The toast itself, over a photo: to the best friend and the topic | `text`: the toast, naming the best friend and the topic, in one short sentence; images: `background` calm-backdrop or backdrop; tags: statement, toast |
| `full-screen-pixabay-deep-wedding` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |
| `quote-wedding` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |

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
| `then-and-now-wedding` | The best friend then and now, as two captioned photos: an old one, and one of them since | the default; `title`: the slide's title, as a wedding toast's slide has it: a few words, or empty for none; `caption_1`: the best friend long ago, in a few words; `caption_2`: the best friend now, in a few words: what the topic made of them; images: `image_1` vintage, else old-photo, else photo, `image_2` portrait, else photo; tags: intro, two_captions |
| `side-by-side-wedding` | The couple side by side, as two captioned photos: the best friend and the topic, each with a trait of theirs, the second one the reason they fit | `title`: the slide's title, as a wedding toast's slide has it: a few words, or empty for none; `caption_1`: the best friend's name and a trait of theirs, in a few words; `caption_2`: the topic's name and the trait that fits it, in a few words; images: `image_1` portrait, else photo, `image_2` photo; tags: couple, two_captions |
| `two-captions-gifs-wedding` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | images: `image_1` neutral or meme-chaos, `image_2` gifs, else weird; tags: gif, multi_caption, two_captions |

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
| `marriage-advice-wedding` | Marriage advice for the couple, as three captioned photos, the last piece the punchline | the default; `title`: the slide's title, as a wedding toast's slide has it: a few words; `caption_1`: a piece of marriage advice, in a few words; `caption_2`: another piece of advice, in a few words; `caption_3`: the last piece, the punchline, in a few words; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: advice, three_captions |

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
| `happiness-since-wedding` | The best friend's happiness since meeting the topic, as a line that climbs, and as a second line that appears on a click, the punchline, something of the speaker's that fell away since (their game nights together, say) | the default; `title`: the chart's claim, about the best friend since they met the topic; `shape`: how the best friend's happiness goes: rising, exponential, hockey stick or plateau; `line`: the best friend's happiness, in the legend; `second_line`: what fell away since, in the legend: the punchline; `second_shape`: how that goes: falling, crash or dip; `event`: the moment they met, where the line takes off; tags: chart, how_they_met, trend_chart |

## `chart_bars`

A ranking in bars, which appear one by one, a click each, from the top down: the first ones tiny, and the last one, the punchline, wins by far.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the question the ranking answers, as its title |
| `bars` | 100 | three or four things (only their names), separated by \|: ordinary ones first, the last one the punchline |
| `value_axis` | 40 | what the bars measure, such as 'Danger level' (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `great-loves-wedding` | The best friend's great loves, ranked in bars: the things they loved before (a snack, a nap, an old bike), and the topic, the last bar, the punchline, which wins by far | the default; `title`: what the ranking compares, about the best friend's loves; `bars`: two or three of the best friend's earlier loves (only their names), separated by \|, and the topic last; `value_axis`: what the bars measure, such as their devotion; tags: bar_chart, chart, couple |

## `venn`

A Venn diagram: two or three circles of things, each with a label, and what's in all of them at once, the punchline, which appears on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the diagram's title |
| `circle_1` | 30 | the first circle's label: a group of things |
| `circle_2` | 30 | the second circle's label: a group of things that seems to have nothing to do with the first |
| `circle_3` | 30 | a third circle's label: another such group (or empty, for none) |
| `overlap` | 30 | the one thing that is in all the circles at once: the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `perfect-match-wedding` | Why the couple is perfect together, as a Venn diagram: the best friend in one circle, the topic in another, maybe a third, and what they all share, the punchline | the default; `title`: the slide's title, as a wedding toast's slide has it: a few words; `circle_1`: the best friend, by the first name the talk gave them (they're 'they'); `circle_2`: the one the best friend marries: the topic, by its name; `overlap`: the odd thing they share; tags: couple, diagram, venn_diagram |

## `social_post`

A made-up social media post with a photo: who posted it, and what they wrote (talkgenerator adds its likes and shares).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |
| `author` | 30 | the made-up name of who posted it: a real first name and a surname |
| `handle` | 24 | their made-up username, without the @ |
| `text` | 90 | the post: what they wrote, in one or two short sentences, without hashtags or emoji |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `that-night-wedding` | A post from the night the couple met: the best friend's, smitten, or the speaker's, about losing their best friend to the topic | the default; `title`: a title such as whose post it was and when, or empty for none; `author`: the best friend's first name, or the speaker's name; images: `photo` photo; tags: social_post, story |

## `timeline`

A timeline of three to five moments, oldest first, each a date and what happened; they appear one by one, a click each, the last one the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the timeline's title |
| `date_1` | 12 | the first moment's date (a year, say, or a day) |
| `event_1` | 32 | what happened at the first moment, in a few words |
| `date_2` | 12 | the second moment's date (a year, say, or a day) |
| `event_2` | 32 | what happened at the second moment, in a few words |
| `date_3` | 12 | the third moment's date (a year, say, or a day) |
| `event_3` | 32 | what happened at the third moment, in a few words |
| `date_4` | 12 | the fourth moment's date (a year, say, or a day) (or empty, for none) |
| `event_4` | 32 | what happened at the fourth moment, in a few words (or empty, for none) |
| `date_5` | 12 | the fifth moment's date (a year, say, or a day) (or empty, for none) |
| `event_5` | 32 | what happened at the fifth moment, in a few words (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `love-story-wedding` | The couple's love story as a timeline, from the first glance to today, the last moment the punchline | the default; `title`: the slide's title, as a wedding toast's slide has it: a few words; `date_1`: when it happened, counted from the day they met (the last one today); `date_2`: when it happened, counted from the day they met (the last one today); `date_3`: when it happened, counted from the day they met (the last one today); `date_4`: when it happened, counted from the day they met (the last one today); `date_5`: when it happened, counted from the day they met (the last one today); `event_1`: what happened then, in a few words; `event_2`: what happened then, in a few words; `event_3`: what happened then, in a few words; `event_4`: what happened then, in a few words; `event_5`: what happened then, in a few words; tags: diagram, how_they_met, timeline |

## `pyramid`

A pyramid of three or four levels, from its top (the rarest, the punchline) down to its base; they appear one by one, a click each, from the base up.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the pyramid's title |
| `level_1` | 30 | the top of the pyramid: the punchline |
| `level_2` | 30 | the level under the top |
| `level_3` | 30 | the level under that (the base, if there's no fourth) |
| `level_4` | 30 | the base, under that (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `happy-marriage-pyramid-wedding` | What a happy marriage is built on, as a pyramid: the basics at its base, and at its top the punchline | the default; `title`: the slide's title, as a wedding toast's slide has it: a few words; tags: advice, diagram, pyramid |

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
| `meme-wedding` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 100 | the fact: one short sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-wedding` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 90 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 90 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `raise-your-glasses-wedding` | The toast, as audience participation: the speaker has the whole room raise their glasses to the couple, the best friend and the topic, and say something together | the default; `audience`: what everyone in the room does and says, said to them, for the toast to the best friend and the topic; no drink named; shows no `dare`; tags: dare, toast |

## `red_flags`

Red flags: three warning signs, each beside a red flag, appearing one by one, a click each, each more alarming than the last: the last one is the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title, which says these are red flags (of what) |
| `flag_1` | 50 | the first red flag, in a few words |
| `flag_2` | 50 | the second red flag, in a few words |
| `flag_3` | 50 | the third red flag, the punchline, in a few words |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `red-flags-we-ignored-wedding` | The red flags everyone ignored, in hindsight: the signs that the best friend was falling for the topic, each more telling than the last, the last one the punchline | the default; `title`: a title that says these are the red flags everyone ignored; tags: red_flags, story |

## `reviews`

Made-up reviews, with stars: two or three reviewers' ratings (one to five stars) and what they wrote, appearing one by one, a click each; the last one, the punchline, is a one-star review most of the time.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title, such as what people are saying (or empty, for none) |
| `stars_1` | 1 | how many stars the first reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_1` | 60 | what the first reviewer wrote, in one short sentence |
| `reviewer_1` | 30 | who the first reviewer is: a real first name, a comma, and a detail (or empty, for none) |
| `stars_2` | 1 | how many stars the second reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_2` | 60 | what the second reviewer wrote, in one short sentence |
| `reviewer_2` | 30 | who the second reviewer is: a real first name, a comma, and a detail (or empty, for none) |
| `stars_3` | 1 | how many stars the third reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` (or empty, for any) |
| `review_3` | 60 | what the third reviewer wrote, in one short sentence (or empty, for none) |
| `reviewer_3` | 30 | who the third reviewer is: a real first name, a comma, and a detail (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `reviews-wedding` | Made-up customer reviews of the concept, as if it were a product: glowing ones that take it far too seriously, then a one-star review, the punchline | the default; tags: reviews |
