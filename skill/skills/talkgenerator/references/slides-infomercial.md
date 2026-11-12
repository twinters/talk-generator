# The slides of an `infomercial` talk

A late-night TV infomercial for a gadget made of the topic: the everyday problem, the gadget, its demonstration, testimonials, the fine print, the price, 'But wait, there's more!' and the call to order now, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format infomercial`.

A plan's `title` is like an infomercial's: the gadget's made-up name and a promise, with an exclamation mark, and its `presenter_job` is their part in the infomercial (its host, the gadget's inventor, a satisfied customer), as the screen introduces them.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `problem` | 1 | `problem-infomercial`, `there-has-to-be-a-better-way-infomercial` |
| `product` | 1 | `as-seen-on-tv-infomercial`, `introducing-infomercial` |
| `demo` | 1 to 2 | `how-it-works-infomercial`, `it-does-it-all-infomercial`, `old-way-new-way-infomercial` |
| `testimonials` | 1 | `before-and-after-infomercial`, `happy-customer-infomercial`, `testimonials-infomercial` |
| `fine_print` | 1 | `terms-and-conditions-infomercial`, `terms-dialog-infomercial` |
| `price` | 1 | `easy-payments-infomercial`, `price-drop-infomercial` |
| `but_wait` | 1 | `but-wait-infomercial`, `double-the-offer-infomercial`, `there-s-more-infomercial` |
| `call_now` | 1 | `call-now-infomercial`, `order-now-infomercial`, `phone-number-infomercial` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `introducing-infomercial` | The gadget, revealed in one photo, under a title that introduces it by its made-up name, as an infomercial does | the default; `title`: a title that introduces the gadget by its made-up name, with an exclamation mark; images: `image` product-shot (or generated, from its prompt, with an image generator set up); tags: product, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `there-has-to-be-a-better-way-infomercial` | The everyday problem the gadget solves, as an infomercial shows it: someone failing at something everyday with the concept, in a photo filling the slide | the default; `title`: the infomercial's cry for a better way, in a few words, with an exclamation mark; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: full_image, problem |
| `as-seen-on-tv-infomercial` | The gadget, in a photo filling the slide, under its made-up name and a promise | `title`: the gadget's made-up name and a few words of promise, with an exclamation mark; images: `image` product-shot (or generated, from its prompt, with an image generator set up); tags: full_image, product |
| `but-wait-infomercial` | But wait, there's more: an odd bonus that comes with the gadget, free, in a photo filling the slide | `title`: 'But wait!' and the bonus you get free if you order now, in a few words, with an exclamation mark; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: but_wait, full_image |
| `full-screen-gif-infomercial` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `full-screen-neutral-images-infomercial` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `provocation-infomercial` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as an infomercial shouts them, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `there-s-more-infomercial` | 'But wait, there's more!', said over a photo, and nothing else: the presenter has to say what more there is | the default; `text`: the words that announce there's more, and nothing more; images: `background` calm-backdrop or backdrop; tags: but_wait, statement |
| `call-now-infomercial` | The call to order now, over a photo of operators standing by | `text`: the call to order now, shouted, in a sentence or two; images: `background` calm-backdrop, else photo; tags: call_now, statement |
| `full-screen-pixabay-deep-infomercial` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |

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
| `old-way-new-way-infomercial` | The old way and the gadget's way, side by side: someone struggling with the concept, and someone delighted with the gadget | the default; `title`: a title that shouts the difference, or empty for none; `caption_1`: the old way, in a few words; `caption_2`: the gadget's way, by its made-up name, with an exclamation mark; images: `image_1` weird-stock, `image_2` photo; tags: demo, two_captions |
| `before-and-after-infomercial` | Before and after the gadget, side by side: a photo of life with the concept before it, an odd one after, under a title that promises results | `title`: a title that promises results, with an exclamation mark; `caption_1`: before, in a few words; `caption_2`: after, in a few words: the punchline; images: `image_1` photo, `image_2` weird-stock; tags: testimonials, two_captions |

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
| `it-does-it-all-infomercial` | What the gadget does, as an infomercial demonstrates it: three photos, each under a caption that shouts what it does, the last one the punchline, something no gadget should do | the default; `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'Watch this!'; `caption_1`: what it does, in two to five words, with an exclamation mark; `caption_2`: something else it does, in two to five words, with an exclamation mark; `caption_3`: the punchline: something no gadget should do, in two to five words; images: `image_1` weird-stock, `image_2` weird-stock, `image_3` weird-stock; tags: demo, three_captions |

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
| `easy-payments-infomercial` | The price, as one big number, in easy payments: what the gadget costs today, and what that gets you | the default; `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'Only'; `number`: the price with its currency, or as payments, such as '3 × $19.99'; `label`: what you get for it, or how to pay it, without the price itself; `source`: the small print, such as shipping and handling, or empty for none; images: `background` backdrop; tags: big_number, price |
| `double-the-offer-infomercial` | But wait, there's more: the offer doubled, as one big number, for anyone who orders in the next few minutes | `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'But wait!'; `number`: how much more you get, such as '2 for 1' or '×2'; `label`: what you get, and the catch, without the number itself; `source`: the small print, such as shipping and handling, or empty for none; images: `background` backdrop; tags: big_number, but_wait |
| `phone-number-infomercial` | The number to call, as one big number: a made-up phone number, and why to call it right now | `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'Call now!'; `number`: a made-up phone number of the 555 kind, such as '555-0199'; `label`: why to call right now, without the number itself; `source`: the small print, such as when the lines close, or empty for none; images: `background` backdrop; tags: big_number, call_now |

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
| `price-drop-infomercial` | The price, as an infomercial reveals it: prices on tiles, each lower than the one before, with what that price would have been, the last one today's price, the punchline | the default; `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'How much would you pay?'; `number_1`: a price with its currency, lower than the one before; `number_2`: a price with its currency, lower than the one before; `number_3`: a price with its currency, lower than the one before; `number_4`: a price with its currency, lower than the one before; `label_1`: what that price would have been, such as in stores; `label_2`: what that price would have been, such as in stores; `label_3`: what that price would have been, such as in stores; `label_4`: what that price would have been, such as in stores; images: `background` backdrop; tags: kpi, price |

## `quiz`

A quiz question for the audience, with three or four options (A to D), which appear one by one, a click each; the answer, and why, appear on the click after them.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 90 | the quiz question |
| `option_a` | 50 | option A (without its letter) |
| `option_b` | 50 | option B |
| `option_c` | 50 | option C |
| `option_d` | 50 | option D (or empty, for none) |
| `answer` | 1 | the letter of the right option: `A`, `B`, `C`, `D` |
| `explanation` | 90 | why that's the answer, shown with it (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `quiz-infomercial` | A quiz question about the concept for the audience: options that all seem possible, and a surprising answer | the default; tags: quiz |

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
| `happy-customer-infomercial` | A happy customer's post about the gadget, far too enthusiastic, about something it shouldn't do | the default; `title`: a title such as 'Our customers love it!', or empty for none; images: `photo` photo; tags: social_post, testimonials |

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
| `news-headline-infomercial` | A made-up news story about the concept, as breaking news | the default; images: `photo` neutral (or generated, from its prompt, with an image generator set up); tags: news |

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
| `how-it-works-infomercial` | How the gadget works, in a few easy steps, the last one the punchline: what life is like once you own one | the default; `title`: the slide's title, as an infomercial shouts it: a few words, with an exclamation mark, such as 'Easy as 1, 2, 3!'; `step_1`: a step, in two to five words; `step_2`: a step, in two to five words; `step_3`: a step, in two to five words; `step_4`: a step, in two to five words; `step_5`: a step, in two to five words; tags: demo, process |

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
| `meme-infomercial` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-infomercial` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 130 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 130 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `order-now-infomercial` | The call to order now, as audience participation: the whole room orders the gadget at once | the default; `audience`: what the presenter has the whole audience do to order the gadget right now, said to them: pretend to dial, wave their phones, shout its name; harmless and singling nobody out; shows no `dare`; tags: call_now, dare |

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
| `tier-list-infomercial` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

## `wall_of_text`

A wall of text that nobody can read: dense points of jargon filling the slide, as nested bullets, with one more point hidden among them, the punchline, which a marker highlights on a click (talkgenerator adds 'Continued on next slide' under it).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title, as if it were all perfectly clear |
| `points` | 2600 | twelve to sixteen points of dense jargon, separated by \|, each a long sentence of fifteen to twenty-five words: the more the better, as nobody is meant to read them |
| `highlight` | 110 | one more point, hidden among the others and highlighted on a click: the punchline, as dense as they are, but absurd |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `terms-and-conditions-infomercial` | The fine print, as a wall of text that nobody can read: dense disclaimers about the gadget, in legalese, and one absurd one hidden among them, the punchline | the default; `title`: a title such as 'Terms and conditions'; tags: fine_print, wall_of_text |

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
| `testimonials-infomercial` | Testimonials of satisfied customers, as five-star reviews: glowing ones, and the last one, the punchline, glowing about something the gadget should never have done | the default; `title`: a title such as 'Real customers!', or empty for none; `stars_1`: 5, as every testimonial here gives; `stars_2`: 5, as every testimonial here gives; `stars_3`: 5, as every testimonial here gives; `reviewer_1`: a made-up first name and an age or a detail, as an infomercial captions them; `reviewer_2`: a made-up first name and an age or a detail, as an infomercial captions them; `reviewer_3`: a made-up first name and an age or a detail, as an infomercial captions them; tags: reviews, testimonials |

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
| `terms-dialog-infomercial` | The terms and conditions, as a dialog everyone must accept before ordering: one absurd clause about the gadget, and buttons that all agree, the last one the punchline | the default; `title`: the dialog's title, such as 'Terms and conditions'; `message`: one absurd clause of the fine print, about the gadget; `code`: the clause's number, absurdly precise; `buttons`: two or three buttons, separated by \|, each at most 20 characters, every one of them agreeing: the last one the punchline; tags: error_message, fine_print |

## `problem`

The problem the talk is about, early on, to hook the audience: a short heading on a sticker, the problem in a few big words, and a short line under it that makes it hit home, which appears on a click; over a picture of it, or beside a picture that shows it.

| Text | At most | What to write |
| --- | --- | --- |
| `kicker` | 28 | a short heading over the problem, in two or three words |
| `problem` | 60 | the problem in a few words, three to eight, not a sentence that explains it: a hook that the audience either recognises at once or can't believe |
| `detail` | 60 | a short line under it, a few words, that makes it hit home (how often it happens, to whom, or what it costs); it appears on a click (or empty, for none) |

Images: `background`, `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `problem-infomercial` | The everyday problem the gadget solves, as an infomercial opens on it: a small frustration with the concept that everyone has, made into a disaster | the default; `kicker`: a short heading over the problem, as an infomercial asks it, such as 'Tired of this?' or 'Sound familiar?'; `detail`: a short line under it, a few words, that makes it worse: how often it happens, or to how many people; it appears on a click; images: `background` calm-backdrop or backdrop, `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: problem, problem_slide |
