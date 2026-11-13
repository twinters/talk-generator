# The slides of a `museum` talk

A guided museum tour of a collection about the topic: the welcome and the house rules, a masterpiece, the artist, the eras, an artefact and the gift shop, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format museum`.

A plan's `title` is like an exhibition's title: grand, with the museum's made-up name or a period of art, and its `presenter_job` is their part at the museum, as the tour's leaflet introduces them (the head guide, the curator of an absurdly specific collection, a volunteer of thirty years).

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `welcome` | 1 | `house-rules-museum`, `the-tour-museum`, `welcome-museum` |
| `masterpiece` | 1 to 2 | `masterpiece-in-full-museum`, `masterpiece-museum`, `the-restoration-museum` |
| `artist` | 1 to 2 | `the-artist-s-life-museum`, `the-artist-s-post-museum`, `the-artist-s-secret-museum` |
| `eras` | 1 to 2 | `the-hierarchy-of-art-museum`, `the-movements-ranked-museum`, `three-periods-museum` |
| `artefact` | 1 | `artefact-museum`, `the-discovery-museum`, `what-was-it-for-museum` |
| `gift_shop` | 1 | `gift-shop-prices-museum`, `gift-shop-special-museum`, `souvenirs-museum` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `masterpiece-museum` | The masterpiece of the collection: a painting of the topic, under its museum label, which the guide admires and explains | the default; `title`: the painting's label: its grand made-up title about the topic and its year, such as 'Penguin at Dawn, 1642'; images: `image` museum, else illustration; tags: labelled_painting, masterpiece, single_image |
| `artefact-museum` | An artefact behind glass: an odd object to do with the topic, under its museum label, which says what nobody knows about it | `title`: the artefact's label: its number and what it might be, such as 'Exhibit 12: use unknown'; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: artefact, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `welcome-museum` | The tour's welcome: the museum's grand hall, filling the slide, under the guide's greeting, which names the museum | the default; `title`: the guide's greeting, which names the museum by a made-up name, in a few words; images: `image` photo, else museum; tags: full_image, welcome |
| `masterpiece-in-full-museum` | The masterpiece, filling the slide: a painting of the topic, under its grand made-up title, for the group to take in | `title`: the painting's grand made-up title about the topic, or a word on what to look at in it; images: `image` museum, else illustration; tags: full_image, full_painting, masterpiece |
| `full-screen-neutral-images-museum` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `full-screen-gif-museum` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `provocation-museum` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a museum's guide or its signs would whisper it, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 90 | the big text over the photo: one short sentence |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-pixabay-deep-museum` | A deep question over a photo | the default; `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |
| `quote-museum` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |

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
| `the-restoration-museum` | The masterpiece before and after its restoration, side by side: the old painting, and a clumsy drawing of the same thing, as a restoration that went wrong left it; the guide is very proud of it | the default; `title`: a title about the restoration, or empty for none; `caption_1`: the painting before its restoration, in two to five words; `caption_2`: the painting after its restoration, in two to five words, as if it went well; images: `image_1` museum, else illustration, `image_2` illustration, else weird-stock; tags: masterpiece, two_captions |

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
| `three-periods-museum` | Three periods of the artist, or of the topic in art, each a work of art with its period's name, the last one the punchline | the default; `title`: a title about the periods, or empty for none; `caption_1`: the first period's name, in two to five words; `caption_2`: the second period's name, in two to five words; `caption_3`: the last period's name, the punchline, in two to five words; images: `image_1` museum, else photo, `image_2` museum, else photo, `image_3` museum, else photo; tags: eras, three_captions |
| `souvenirs-museum` | Three souvenirs of the topic from the gift shop, each a photo with a caption, the last one the punchline | `title`: the slide's title, as a museum's sign or its guide would say it: a few words, such as 'Take it home'; `caption_1`: a souvenir, in two to five words; `caption_2`: another souvenir, in two to five words; `caption_3`: the last souvenir, the punchline, in two to five words; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: gift_shop, three_captions |

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
| `gift-shop-special-museum` | The gift shop's special, as one big price: far too much for a small souvenir of the topic | the default; `title`: the slide's title, as a museum's sign or its guide would say it: a few words, such as 'In the gift shop'; `number`: the price, with its currency, such as '€45'; `label`: what the price buys, without the price itself: a small souvenir of the topic; `source`: the small print, such as 'Members get 5% off'; images: `background` backdrop; tags: big_number, gift_shop |

## `kpi`

Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; they appear one by one, a click each, the last one the punchline; over a picture of what they're about, if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the dashboard's title |
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
| `gift-shop-prices-museum` | The gift shop's prices, on tiles, as the tour ends: souvenirs of the topic and what they cost, from the cheapest to the last one, the punchline | the default; `title`: the slide's title, as a museum's sign or its guide would say it: a few words, such as 'The gift shop'; `number_1`: the price, with its currency, such as '€45'; `number_2`: the price, with its currency, such as '€45'; `number_3`: the price, with its currency, such as '€45'; `number_4`: the price, with its currency, such as '€45'; `label_1`: what the price buys, without the price itself, in a few words; `label_2`: what the price buys, without the price itself, in a few words; `label_3`: what the price buys, without the price itself, in a few words; `label_4`: what the price buys, without the price itself, in a few words; images: `background` backdrop; tags: gift_shop, kpi |

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
| `what-was-it-for-museum` | A quiz for the group on what people once used the topic for: three or four odd uses, and the museum's own answer, the punchline, which is the right one | the default; `explanation`: the museum's reason for its answer, without naming any of the options; tags: artefact, quiz |

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
| `the-artist-s-post-museum` | A post by the artist, a made-up old master (never a real artist), as if they had social media centuries ago: their frustrations with painting the topic, beside one of their works | the default; `title`: a title such as 'From the artist's diary', or empty for none; `author`: the artist's made-up name, as an old master's; `text`: the post: what the artist wrote, in the voice of an old master, about the topic; images: `photo` museum, else photo; tags: artist, social_post |

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
| `the-discovery-museum` | The news of the artefact's discovery, as an art paper or the evening news had it: where an odd object to do with the topic was found, and what the experts make of it | the default; `outlet`: the made-up name of an art paper or a news channel; images: `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: artefact, news |

## `agenda`

The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the agenda's title |
| `items` | 150 | three to five items, separated by \|, each at most 30 characters |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `house-rules-museum` | The museum's house rules, before the tour begins: three or four rules, numbered, the last one the punchline, an odd rule that only this museum would need | the default; `title`: the rules' title, such as 'House rules'; `items`: three or four rules, separated by \|, each at most 30 characters: the last one the punchline; tags: agenda, welcome |
| `the-tour-museum` | The tour's stops, in order: three or four rooms of the museum, the last one the gift shop, or another punchline | `title`: the tour's title, such as 'Today's tour'; `items`: three or four stops, separated by \|, each at most 30 characters: the last one the punchline; tags: agenda, welcome |

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
| `the-artist-s-life-museum` | The life of the artist, a made-up old master (never a real artist), as a timeline, oldest first: from their birth to their obsession with the topic, the last moment the punchline | the default; `title`: the timeline's title, which names the artist by their made-up name; `event_1`: what happened in the artist's life then, in two to five words; `event_2`: what happened in the artist's life then, in two to five words; `event_3`: what happened in the artist's life then, in two to five words; `event_4`: what happened in the artist's life then, in two to five words; `event_5`: what happened in the artist's life then, in two to five words; tags: artist, diagram, history, timeline |

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
| `the-hierarchy-of-art-museum` | The hierarchy of art as a pyramid, as the guide sees it: the topic at the very top, the punchline, and the humblest art there is at the base | the default; `title`: the pyramid's title, such as 'The hierarchy of art'; tags: diagram, eras, pyramid |

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
| `meme-museum` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 100 | the fact: one short sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-artist-s-secret-museum` | A fun fact about the artist, a made-up old master (never a real artist): an odd habit or a scandal, about the topic, stated as certain, beside one of their works | the default; `fact`: the fact about the artist, by their made-up name: one sentence, stated as certain; `source`: a made-up, unreliable source, such as the museum's audio guide; images: `photo` museum, else photo; tags: artist, fun_fact |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 90 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 90 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `dare-museum` | A dare, halfway through the talk | the default; tags: dare |

## `tier_list`

A tier list: things ranked in tiers from S (the best) to F (the worst), one thing in a tier; the tiers fill one by one, a click each, from the worst up to the S tier, the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the tier list's title |
| `s_tier` | 28 | the S tier, the very best: one surprising thing, the punchline |
| `a_tier` | 28 | the A tier: one thing |
| `b_tier` | 28 | the B tier: one thing (or empty, for none) |
| `c_tier` | 28 | the C tier: one thing (or empty, for none) |
| `f_tier` | 28 | the F tier, the worst: one thing (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-movements-ranked-museum` | The art movements, ranked by the guide in a tier list: real ones and made-up ones, with the topic's own movement in the S tier, the punchline | the default; `title`: the tier list's title, such as 'Art movements, ranked'; `s_tier`: the topic's own art movement, named after it, such as 'Penguinism': the punchline; tags: eras, tier_list |

## `alignment_chart`

An alignment chart, as Dungeons & Dragons sorts characters: nine things in a grid of three by three, from lawful to chaotic across and from good to evil down (talkgenerator adds the axes' words), which appear one by one, a click each, in reading order: chaotic evil, the punchline, last.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the alignment chart's title |
| `lawful_good` | 32 | the lawful good one, in a few words |
| `neutral_good` | 32 | the neutral good one, in a few words |
| `chaotic_good` | 32 | the chaotic good one, in a few words |
| `lawful_neutral` | 32 | the lawful neutral one, in a few words |
| `true_neutral` | 32 | the true neutral one, in a few words |
| `chaotic_neutral` | 32 | the chaotic neutral one, in a few words |
| `lawful_evil` | 32 | the lawful evil one, in a few words |
| `neutral_evil` | 32 | the neutral evil one, in a few words |
| `chaotic_evil` | 32 | the chaotic evil one, in a few words: the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `alignment-chart-museum` | An alignment chart of things to do with the concept, as Dungeons & Dragons sorts characters: harmless and wholesome as lawful good, unhinged as chaotic evil, the punchline | the default; tags: alignment_chart |

## `reviews`

Made-up reviews, with stars: two or three reviewers' ratings (one to five stars) and what they wrote, appearing one by one, a click each; the last one, the punchline, is a one-star review most of the time.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title, such as what people are saying (or empty, for none) |
| `stars_1` | 1 | how many stars the first reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_1` | 70 | what the first reviewer wrote, in one short sentence |
| `reviewer_1` | 30 | who the first reviewer is: a real first name, a comma, and a detail (or empty, for none) |
| `stars_2` | 1 | how many stars the second reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` |
| `review_2` | 70 | what the second reviewer wrote, in one short sentence |
| `reviewer_2` | 30 | who the second reviewer is: a real first name, a comma, and a detail (or empty, for none) |
| `stars_3` | 1 | how many stars the third reviewer gives, from 1 to 5: `1`, `2`, `3`, `4`, `5` (or empty, for any) |
| `review_3` | 70 | what the third reviewer wrote, in one short sentence (or empty, for none) |
| `reviewer_3` | 30 | who the third reviewer is: a real first name, a comma, and a detail (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `reviews-museum` | Made-up customer reviews of the concept, as if it were a product: glowing ones that take it far too seriously, then a one-star review, the punchline | the default; tags: reviews |
