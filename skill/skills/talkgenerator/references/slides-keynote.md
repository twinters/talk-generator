# The slides of a `keynote` talk

A product keynote on a big stage: a big opening statement, the one idea, the reveal of the product, its features, a live demo, the price, the 'one more thing' and a closing line, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format keynote`.

A plan's `title` is like a product keynote's title: the product's made-up name and a grand promise, in a few words, and its `presenter_job` is their role at the company launching the product, as a keynote introduces them.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `opening` | 1 | `opening-image-keynote`, `opening-number-keynote`, `opening-statement-keynote` |
| `idea` | 1 | `the-one-idea-keynote`, `where-it-all-meets-keynote` |
| `reveal` | 1 | `introducing-keynote`, `product-shot-keynote` |
| `features` | 1 to 2 | `faster-than-ever-keynote`, `specs-keynote`, `three-features-keynote` |
| `demo` | 1 | `demo-crash-keynote`, `how-it-works-keynote`, `live-demo-keynote` |
| `price` | 1 | `availability-keynote`, `models-and-prices-keynote`, `price-keynote` |
| `one_more_thing` | 1 | `one-more-thing-keynote`, `one-more-thing-reveal-keynote` |
| `closing` | 1 | `audience-reaction-keynote`, `closing-image-keynote`, `closing-line-keynote` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `introducing-keynote` | The reveal: the product, in one photo, under a title that introduces it by its made-up name | the default; `title`: a title that introduces the product by its made-up name, such as 'Introducing ...'; images: `image` product-shot (or generated, from its prompt, with an image generator set up); tags: reveal, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `opening-image-keynote` | The keynote's opening: a striking photo of the topic, filling the slide, under a greeting | the default; `title`: the greeting, in a few words, as a keynote shows them huge, such as 'Good morning.'; images: `image` photo; tags: full_image, opening |
| `product-shot-keynote` | The reveal: the product, in a photo filling the slide, with its made-up name as the title | `title`: the product's made-up name, and a few words of your own about it; images: `image` product-shot (or generated, from its prompt, with an image generator set up); tags: full_image, reveal |
| `live-demo-keynote` | The live demo: an odd photo, filling the slide, that the presenter has to present as the demo | `title`: a title such as 'Live demo'; images: `image` weird-stock; tags: demo, full_image |
| `one-more-thing-reveal-keynote` | The 'one more thing': a second, stranger product, revealed in an odd photo filling the slide | `title`: 'One more thing:' and then the second product, by a made-up name of its own; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: full_image, one_more_thing |
| `closing-image-keynote` | The keynote's closing: a striking photo of the topic, filling the slide, under its last words | `title`: the last words, in a few words, as a keynote shows them huge, such as 'Thank you.'; images: `image` photo; tags: closing, full_image |
| `full-screen-neutral-images-keynote` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `full-screen-gif-keynote` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `provocation-keynote` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a keynote announces a product, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `opening-statement-keynote` | The keynote's big opening statement, over a photo: that today, everything changes for the topic | the default; `text`: the opening statement, as one sentence in a few words, as a keynote shows them huge; images: `background` calm-backdrop or backdrop; tags: opening, statement |
| `the-one-idea-keynote` | The keynote's one idea, as a bold question over a photo: what if the topic were completely different | `text`: the one idea, as a question in a few words, as a keynote shows them huge; images: `background` calm-backdrop or backdrop; tags: idea, statement |
| `one-more-thing-keynote` | The 'one more thing', said over a photo, just as the keynote seems over: the presenter has to say what the thing is | `text`: the words that announce one more thing, and nothing more; images: `background` calm-backdrop or backdrop; tags: one_more_thing, statement |
| `closing-line-keynote` | The keynote's closing line, over a photo: the product, and what it means for the world | `text`: the closing line, in a few words, as a keynote shows them huge; images: `background` calm-backdrop or backdrop; tags: closing, statement |
| `full-screen-pixabay-deep-keynote` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |
| `quote-keynote` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |

## `two_columns`

Two captioned images side by side.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `caption_1` | 40 | the left caption |
| `caption_2` | 40 | the right caption |

Images: `image_1`, `image_2`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `two-captions-copyright-free` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; images: `image_2` photo or weird-stock; tags: multi_caption, two_captions |

## `three_columns`

Three captioned images side by side.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `caption_1` | 40 | the left caption |
| `caption_2` | 40 | the middle caption |
| `caption_3` | 40 | the right caption |

Images: `image_1`, `image_2`, `image_3`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `three-features-keynote` | Three of the product's features, each a photo of what it does with a caption, the last one the punchline | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Three things you'll love'; `caption_1`: a feature, in two to four words; `caption_2`: another feature, in two to four words; `caption_3`: the last feature, the punchline, in two to four words; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: features, three_captions |

## `history_quote`

A made-up historical figure's portrait, next to their quote.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | a title about history |
| `name` | 60 | a made-up historical figure (never a real person): name and title |
| `quote` | 160 | what this made-up figure once said |

Images: `portrait`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `historical-figure-quote-crf` | What a made-up historical figure once said about the slide's concept | the default; images: `portrait` portrait (or generated, from its prompt, with an image generator set up); tags: history, quote |

## `chart_bars`

A ranking in bars, whose last bar, the punchline, wins by far.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 90 | the question the ranking answers, as its title |
| `bars` | 160 | three to six things (only their names), separated by \|, the last one the punchline |
| `value_axis` | 40 | what the bars measure, such as 'Danger level' (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `faster-than-ever-keynote` | How much better the product is, as a ranking in bars that it wins by far: what came before it (the old product, the competition, an odd thing), and the product, the last bar | the default; `title`: what the ranking compares, as a keynote's chart has it; `bars`: two to four things (only their names), separated by \|, and the product's made-up name last; `value_axis`: the measure, such as 'Speed' or 'Joy'; tags: bar_chart, chart, features |

## `venn`

A Venn diagram: two or three circles of things, each with a label, and what's in all of them at once, the punchline, which appears on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the diagram's title |
| `circle_1` | 30 | the first circle's label: a group of things |
| `circle_2` | 30 | the second circle's label: a group of things that seems to have nothing to do with the first |
| `circle_3` | 30 | a third circle's label: another such group (or empty, for none) |
| `overlap` | 30 | the one thing that is in all the circles at once: the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `where-it-all-meets-keynote` | The keynote's one idea, as a Venn diagram: the topic and one or two things that seem to have nothing to do with it, and the product where they all meet, the punchline | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'The idea'; `overlap`: the product, by its made-up name; tags: idea, venn_diagram |

## `big_number`

A big, made-up number, with what it counts under it: a figure the presenter has to explain; over a picture of what it's about, or beside it, if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `number` | 12 | the big number, with its unit if it has one: a percentage, an amount or a count |
| `label` | 90 | what the number counts or measures, in a few words |
| `source` | 60 | a made-up, unreliable source for the number (or empty, for none) |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `opening-number-keynote` | The keynote's opening, as one huge number: how well the company has done since its last keynote | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Since last year'; `number`: the number as people read it, with its unit, such as '2 billion' or '18 h'; `label`: what the number measures, without the number itself; `source`: a made-up, unreliable source, or empty for none; images: `background` backdrop; tags: big_number, opening |
| `price-keynote` | The price, as one big number: what the product costs, and what that gets you | `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Pricing'; `number`: the price with its currency, such as '$999'; `label`: what it gets you, or how to pay it, without the price itself; `source`: the small print, such as its colours; images: `background` backdrop; tags: big_number, price |

## `kpi`

Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; they appear one by one, a click each, the last one the punchline; over a picture of what they're about, if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the dashboard's title |
| `number_1` | 10 | the first figure's number, with its unit if it has one |
| `label_1` | 40 | what the first figure measures |
| `number_2` | 10 | the second figure's number, with its unit if it has one |
| `label_2` | 40 | what the second figure measures |
| `number_3` | 10 | the third figure's number, with its unit if it has one |
| `label_3` | 40 | what the third figure measures |
| `number_4` | 10 | the fourth figure's number, with its unit if it has one (or empty, for none) |
| `label_4` | 40 | what the fourth figure measures (or empty, for none) |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `specs-keynote` | The product's specs, as figures on tiles: each a number with its unit and what it measures, the last one the punchline | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Specs'; `number_1`: the spec's number with its unit, such as '2×' or '18 h'; `number_2`: the spec's number with its unit, such as '2×' or '18 h'; `number_3`: the spec's number with its unit, such as '2×' or '18 h'; `number_4`: the spec's number with its unit, such as '2×' or '18 h'; `label_1`: what the number measures, without the number itself; `label_2`: what the number measures, without the number itself; `label_3`: what the number measures, without the number itself; `label_4`: what the number measures, without the number itself; images: `background` backdrop; tags: features, kpi |
| `models-and-prices-keynote` | The models and their prices, on tiles: each a price and who the model is for, from the cheapest to the last one, the punchline | `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Choose yours'; `number_1`: the model's price, with its currency; `number_2`: the model's price, with its currency; `number_3`: the model's price, with its currency; `number_4`: the model's price, with its currency; `label_1`: the model, and who it's for, without its price; `label_2`: the model, and who it's for, without its price; `label_3`: the model, and who it's for, without its price; `label_4`: the model, and who it's for, without its price; images: `background` backdrop; tags: kpi, price |

## `social_post`

A made-up social media post with a photo: who posted it, and what they wrote (talkgenerator adds its likes and shares).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `author` | 30 | the made-up name of who posted it (never a real person) |
| `handle` | 24 | their made-up username, without the @ |
| `text` | 160 | the post: what they wrote, without hashtags or emoji |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `audience-reaction-keynote` | Someone's post about the keynote, as it ends: thrilled, or thrilled about the wrong thing | the default; `title`: a title such as 'What people are saying', or empty for none; images: `photo` photo; tags: closing, social_post |

## `news_headline`

A made-up news story with a photo, as breaking news on television or on a newspaper's front page.

| Text | At most | What to write |
| --- | --- | --- |
| `outlet` | 30 | the made-up name of the newspaper or the channel |
| `headline` | 90 | the headline |
| `subheadline` | 100 | a line under the headline, with more of the story (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `news-headline-keynote` | A made-up news story about the concept, as breaking news | the default; images: `photo` neutral (or generated, from its prompt, with an image generator set up); tags: news |

## `timeline`

A timeline of three to five moments, oldest first, each a date and what happened; they appear one by one, a click each, the last one the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the timeline's title |
| `date_1` | 12 | the first moment's date (a year, say, or a day) |
| `event_1` | 40 | what happened at the first moment |
| `date_2` | 12 | the second moment's date (a year, say, or a day) |
| `event_2` | 40 | what happened at the second moment |
| `date_3` | 12 | the third moment's date (a year, say, or a day) |
| `event_3` | 40 | what happened at the third moment |
| `date_4` | 12 | the fourth moment's date (a year, say, or a day) (or empty, for none) |
| `event_4` | 40 | what happened at the fourth moment (or empty, for none) |
| `date_5` | 12 | the fifth moment's date (a year, say, or a day) (or empty, for none) |
| `event_5` | 40 | what happened at the fifth moment (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `availability-keynote` | When the product is available: from pre-orders today, soonest first, to the last moment, the punchline | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'Availability'; `event_1`: what happens then, in two to four words; `event_2`: what happens then, in two to four words; `event_3`: what happens then, in two to four words; `event_4`: what happens then, in two to four words; `event_5`: what happens then, in two to four words; tags: price, timeline |

## `process`

A process of three to five steps, each leading to the next by an arrow, from the first to the last, the punchline; they appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the process's title |
| `step_1` | 40 | the first step |
| `step_2` | 40 | the second step |
| `step_3` | 40 | the third step (the last, the punchline, if there are no more) |
| `step_4` | 40 | a fourth step (or empty, for none) |
| `step_5` | 40 | a fifth step (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `how-it-works-keynote` | The demo, as how the product works, step by step, the last one the punchline: a step that nobody can explain, or that gives the game away | the default; `title`: the slide's title, as a keynote's slide has it: a few words, such as 'How it works'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: demo, process |

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
| `meme-keynote` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-keynote` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

## `dare`

A dare for the presenter, on a card: a playful task for the next slide or the rest of the talk, which the audience then watches them do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 130 | the task, said to the presenter: a way of speaking, a word to work in, a voice; for the presenter alone, and nothing physical |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `dare-keynote` | A dare for the presenter, halfway through the talk: something playful they now have to do on the next slide or for the rest of the talk | the default; tags: dare |

## `tier_list`

A tier list: things ranked in tiers from S (the best) to F (the worst), one to three in a tier; the tiers fill one by one, a click each, from the worst up to the S tier, the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the tier list's title |
| `s_tier` | 70 | the S tier, the very best: one surprising thing, the punchline |
| `a_tier` | 70 | the A tier: one to three things, separated by \| |
| `b_tier` | 70 | the B tier: one to three things, separated by \| (or empty, for none) |
| `c_tier` | 70 | the C tier: one to three things, separated by \| (or empty, for none) |
| `f_tier` | 70 | the F tier, the worst: one to three things, separated by \| (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `tier-list-keynote` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

## `reviews`

Made-up reviews, with stars: two or three reviewers' ratings (one to five stars) and what they wrote, appearing one by one, a click each; the last one, the punchline, is a one-star review most of the time.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title, such as what people are saying (or empty, for none) |
| `stars_1` | 1 | how many stars the first reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_1` | 110 | what the first reviewer wrote |
| `reviewer_1` | 30 | who the first reviewer is: a made-up first name, and a detail (or empty, for none) |
| `stars_2` | 1 | how many stars the second reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_2` | 110 | what the second reviewer wrote |
| `reviewer_2` | 30 | who the second reviewer is: a made-up first name, and a detail (or empty, for none) |
| `stars_3` | 1 | how many stars the third reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` (or empty, for any) |
| `review_3` | 110 | what the third reviewer wrote (or empty, for none) |
| `reviewer_3` | 30 | who the third reviewer is: a made-up first name, and a detail (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `reviews-keynote` | Made-up customer reviews of the concept, as if it were a product: glowing ones that take it far too seriously, then a one-star review, the punchline | the default; tags: reviews |

## `error_message`

A fake error message, as if the talk itself crashed: a dialog with a title, an absurd message, an error code and two or three buttons, the last one the punchline (talkgenerator adds the warning sign).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 30 | the dialog's title, as in its title bar (or empty, for none) |
| `message` | 120 | the error message |
| `code` | 24 | an error code, made up and absurdly precise (or empty, for none) |
| `buttons` | 66 | two or three of the dialog's buttons, separated by \|, each at most 20 characters: the last one the punchline, an absurd choice of the talk's own |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `demo-crash-keynote` | The live demo, which crashes: a fake error message from the product, in the middle of the keynote, with its buttons, the last one the punchline | the default; `title`: the dialog's title, such as the product's made-up name; `buttons`: two or three buttons, separated by \|, each at most 20 characters: the last one the punchline, such as a way to save the demo; tags: demo, error_message |
