# The slides of a `book_report` talk

A school book report on a book about the topic: the book, its author, the main characters, what happens, the favourite part, the moral of the story and the rating, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format book_report`.

A plan's `title` is like a book report's title: 'My Book Report:' and the book's made-up title, and its `presenter_job` is their year and class at school, as a pupil gives them on a book report.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `book` | 1 | `book-cover-book-report`, `the-book-book-report`, `the-book-in-numbers-book-report` |
| `author` | 1 | `about-the-author-book-report`, `the-author-book-report` |
| `characters` | 1 | `main-characters-book-report`, `who-s-who-book-report` |
| `plot` | 1 to 2 | `how-exciting-it-is-book-report`, `page-by-page-book-report`, `what-happens-book-report` |
| `favourite` | 1 | `favourite-part-book-report`, `my-favourite-part-book-report` |
| `moral` | 1 | `the-moral-book-report`, `what-we-learned-book-report` |
| `rating` | 1 | `my-rating-book-report`, `what-the-class-said-book-report` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-book-book-report` | The book the report is on: its cover, in one photo, under a title that names the book | the default; `title`: a title that names the book by its made-up title, such as 'My Book Report:' and it; images: `image` book-covers, else illustration (or generated, from its prompt, with an image generator set up); tags: book, single_image |
| `the-author-book-report` | The book's made-up author, in one portrait, under a title that introduces them | `title`: a title that introduces the author by their made-up name, such as 'About the author:'; images: `image` portrait (or generated, from its prompt, with an image generator set up); tags: author, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `book-cover-book-report` | The book's cover, filling the slide, under its made-up title and author | the default; `title`: the book's made-up title, and who wrote it, in a few words; images: `image` book-covers, else illustration (or generated, from its prompt, with an image generator set up); tags: book, full_image |
| `my-favourite-part-book-report` | The pupil's favourite part of the book: an odd photo of it, filling the slide, under a title that says it's their favourite part | `title`: a title that says it's the favourite part, in a few words; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: favourite, full_image |
| `full-screen-gif-book-report` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `full-screen-neutral-images-book-report` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `provocation-book-report` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a pupil reads them out, wide-eyed, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `favourite-part-book-report` | The pupil's favourite part of the book, said over a photo, earnestly, with too much detail or too little | the default; `text`: the favourite part, in a pupil's short, earnest sentences, starting with 'My favourite part was'; images: `background` calm-backdrop or backdrop; tags: favourite, statement |
| `the-moral-book-report` | The moral of the story, as the pupil understood it, said over a photo: earnest, and a little off | `text`: the moral of the story, in a pupil's short, earnest sentences, starting with 'The moral of the story is'; images: `background` calm-backdrop or backdrop; tags: moral, statement |
| `full-screen-pixabay-deep-book-report` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |

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
| `two-captions-gifs-book-report` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; images: `image_1` neutral or meme-chaos, `image_2` gifs, else weird; tags: gif, multi_caption, two_captions |

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
| `main-characters-book-report` | The book's main characters, each a photo with a caption that says who they are, the last one the punchline, such as someone who isn't in the book at all | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'The main characters'; `caption_1`: a character, and who they are in the book, in two to five words; `caption_2`: another character, in two to five words; `caption_3`: the last character, the punchline, in two to five words; images: `image_1` weird-stock, `image_2` weird-stock, `image_3` weird-stock; tags: characters, three_captions |

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

## `chart_trend`

A line chart of a made-up trend along two odd axes; a second line, if any, draws itself across it on a click, as the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 90 | the chart's claim, as its title, in a few words: what it shows, such as a headline would say it, never 'X vs Y' (the two things it compares go on its axes) |
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
| `how-exciting-it-is-book-report` | How exciting the book is, page by page, as a line chart with the twist marked on it; a second line, if any, someone else's, such as the pupil's little brother's, as the punchline | the default; `title`: what the chart shows, as a pupil puts it, such as 'How exciting the book is'; `x_axis`: the book's pages or chapters, such as 'Page'; `y_axis`: how exciting it is, in the pupil's words; `line`: the line's name in the legend, such as 'Excitement'; `second_line`: someone else's line, such as 'My little brother', who appears on a click; `event`: the twist, or another moment of the book, marked on the line, in a few words; tags: chart, plot, trend_chart |

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
| `my-rating-book-report` | The pupil's rating of the book, as one big score, with why under it | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'My rating'; `number`: the score, such as '7/10' or '4 stars'; `label`: why that score, in a pupil's words, without the score itself; `source`: who gave the score, such as the pupil and their age; images: `background` backdrop; tags: big_number, rating |

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
| `the-book-in-numbers-book-report` | The book in numbers, on tiles, as a pupil counted them: its pages, its pictures and the like, each a number and what it counts, the last one the punchline, such as how many pages the pupil really read | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'The book in numbers'; `number_1`: the number, such as '212'; `number_2`: the number, such as '212'; `number_3`: the number, such as '212'; `number_4`: the number, such as '212'; `label_1`: what the number counts, without the number itself; `label_2`: what the number counts, without the number itself; `label_3`: what the number counts, without the number itself; `label_4`: what the number counts, without the number itself; images: `background` backdrop; tags: book, kpi |

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
| `what-we-learned-book-report` | A quiz for the class about the book's lesson: what we learned from it, with three or four options, and the lesson the pupil took from it as the answer | the default; `question`: the quiz question about the book's lesson, such as 'What did we learn from this book?'; `explanation`: why that's the lesson, as the pupil is sure of it; tags: moral, quiz |

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
| `page-by-page-book-report` | What happens in the book, page by page, the first pages first, the last moment the punchline | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'The story, page by page'; `date_1`: a page of the book, such as 'Page 12'; `date_2`: a page of the book, such as 'Page 12'; `date_3`: a page of the book, such as 'Page 12'; `date_4`: a page of the book, such as 'Page 12'; `date_5`: a page of the book, such as 'Page 12'; `event_1`: what happens there, in two to five words; `event_2`: what happens there, in two to five words; `event_3`: what happens there, in two to five words; `event_4`: what happens there, in two to five words; `event_5`: what happens there, in two to five words; tags: plot, timeline |

## `org_chart`

A small org chart: who's in charge (the punchline), over two to four people or things, who appear one by one, a click each, and who's in charge on the click after them.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the org chart's title |
| `boss` | 30 | who's in charge: the punchline |
| `report_1` | 30 | the first one under them |
| `report_2` | 30 | the second one under them |
| `report_3` | 30 | a third one under them (or empty, for none) |
| `report_4` | 30 | a fourth one under them (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `who-s-who-book-report` | Who's who in the book, as an org chart: the book's characters, under who's really in charge, the punchline | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'Who's who in the book'; `boss`: who's really in charge in the book, in a few words: the punchline; `report_1`: a character of the book, in a few words; `report_2`: a character of the book, in a few words; `report_3`: a character of the book, in a few words; `report_4`: a character of the book, in a few words; tags: characters, org_chart |

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
| `what-happens-book-report` | What happens in the book, step by step, as a pupil retells it: the last step the punchline, such as how it ends, or where the pupil stopped reading | the default; `title`: the slide's title, as a pupil's book report has it: a few plain words, such as 'What happens'; `step_1`: what happens, in two to five words; `step_2`: what happens, in two to five words; `step_3`: what happens, in two to five words; `step_4`: what happens, in two to five words; `step_5`: what happens, in two to five words; tags: plot, process |

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
| `meme-book-report` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `about-the-author-book-report` | A fun fact about the book's made-up author, with their portrait: something odd about them, or about how they wrote the book, as the pupil read it on the back cover | the default; `fact`: the fact about the author, by their made-up name, in one sentence, stated as certain; `source`: where the pupil read it, such as the back of the book; images: `photo` portrait (or generated, from its prompt, with an image generator set up); tags: author, fun_fact |
| `fun-fact-book-report` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | images: `photo` neutral or meme-chaos; tags: fun_fact |

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
| `tier-list-book-report` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

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
| `what-the-class-said-book-report` | What the pupil's class said about the book, as reviews with stars: kind ones, and the last one, the punchline, a one-star review | the default; `title`: a title such as 'What my class thinks', or empty for none; `reviewer_1`: who in the class wrote it: a made-up first name, and a detail; `reviewer_2`: who in the class wrote it: a made-up first name, and a detail; `reviewer_3`: who in the class wrote it: a made-up first name, and a detail; tags: rating, reviews |
