# The slides of a `ted` talk

A TED-like talk with copyright-free images only (stock photos, artworks and old photos), for decks shown in public; it has no full-screen images, gifs or memes, and no recipes for slides about the presenter.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format ted`.

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `single-image-copyright-free` | A photo with a title | the default; images: `image` photo; tags: single_image |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-pixabay-deep` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |
| `full-screen-pixabay-quote` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: full_image, quote |
| `wikihow-bold-statement-crf` | A bold statement over a photo | the default; `text`: a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'; images: `background` calm-backdrop or backdrop; tags: bold_statement, statement |
| `quote-crf` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |
| `anecdote-crf` | A personal anecdote the presenter now has to tell | `text`: the title of the anecdote, such as 'The time I ...'; images: `background` calm-backdrop or backdrop; tags: anecdote |

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
| `two-history-pictures-crf` | Two old photos from the history of the slide's concept | `title`: a title about the concept's history; `caption_1`: a moment from long ago; `caption_2`: a later moment; images: `image_1` vintage (or generated, from its prompt, with an image generator set up), `image_2` vintage (or generated, from its prompt, with an image generator set up); tags: history, two_images |
| `two-captions-copyright-free` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; images: `image_2` photo or weird-stock; tags: multi_caption, two_captions |
| `2-conclusions-crf` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number or key); `caption_2`: a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number or key); images: `image_1` photo, `image_2` weird-stock; tags: conclusion |

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
| `three-captions-weird-crf` | Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan | the default; images: `image_1` photo, `image_3` weird-stock; tags: multi_caption, three_captions |
| `3-conclusions-crf` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number or key); `caption_2`: a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number or key); `caption_3`: a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number or key); images: `image_1` photo, `image_3` weird-stock; tags: conclusion |

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

## `chart_yes_no`

A chart of answers to a yes-or-no question: yes, no, and a funny third answer.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 90 | a yes-or-no question, as the chart's title |
| `funny_answer` | 30 | a third answer, besides yes and no: an odd one of your own for this question |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `yes-no-funny-chart` | A survey of the audience's opinion about the concept | the default; tags: chart, pie_chart, yes_no_chart |

## `chart_categories`

A pie chart of made-up shares.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 90 | the question the pie chart answers, as its title |
| `categories` | 120 | two to five answers, separated by \| |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `location-chart` | Where the concept is found | `question`: a question such as 'Where do we find ...?'; `categories`: two to five places, separated by \|; tags: chart, location_chart, pie_chart |
| `property-chart` | What the concept is like | the default; `question`: a question such as 'What are ... like?'; `categories`: two to five properties, separated by \|; tags: chart, pie_chart, property_chart |

## `chart_correlation`

A scatter plot of made-up data, under a claim of a correlation: one cloud of points in a shape (now and then with a line fitted through it), or two or three named groups of points, each in its own colour.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 90 | a made-up correlation between two things, as a claim in a few words: what it shows, such as a headline would say it, never 'X vs Y' (the two things it compares go on its axes) |
| `x_axis` | 40 | the axis along the bottom: the first of the two things (or empty, for none) |
| `y_axis` | 40 | the axis going up: the second thing (or empty, for none) |
| `shape` | 12 | the shape of the cloud of points, the funniest one for the claim: `rising`, `falling`, `exponential`, `saturating`, `u-shaped`, `hill`, `wave`, `step`, `none`, `ring`, `smile` (or empty, for any) |
| `cluster_1` | 24 | the name of the first group of points, in the legend (or empty, for none) |
| `cluster_2` | 24 | the name of the second group of points, in the legend (or empty, for none) |
| `cluster_3` | 24 | the name of the third group of points, in the legend (or empty, for none) |
| `outlier` | 30 | one point far above the others, named after someone or something that doesn't belong there (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `correlation-curve` | A made-up scientific finding about the concept | the default; tags: chart, curve |

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
| `trend-chart` | A made-up trend about the concept along two odd axes, with a second line as the punchline when that's funnier | the default; tags: chart, trend_chart |

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
| `bar-ranking` | A ranking that the concept wins by far | the default; tags: bar_chart, chart |

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
| `venn-diagram` | A Venn diagram about the concept: groups of things that seem to have nothing in common, and what they share, as the punchline | the default; tags: diagram, venn_diagram |

## `matrix`

A 2×2 matrix: two axes of everyday opposites that cross in the middle, with a word or two at each end, a short name in each quadrant (or familiar things as dots where they belong, or neither), and one dot with a name, the punchline, which appears on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the matrix's title |
| `x_left` | 24 | the left end of the axis along the bottom: a word or two |
| `x_right` | 24 | the right end of that axis, a word or two: the opposite of the left end |
| `y_bottom` | 24 | the bottom end of the axis going up: a word or two |
| `y_top` | 24 | the top end of that axis, a word or two: the opposite of the bottom end |
| `top_left` | 30 | a short name for the top left quadrant, a word or two: what is both like the top end and like the left end (or empty, for none) |
| `top_right` | 30 | a short name for the top right quadrant, a word or two: what is both like the top end and like the right end (or empty, for none) |
| `bottom_left` | 30 | a short name for the bottom left quadrant, a word or two: what is both like the bottom end and like the left end (or empty, for none) |
| `bottom_right` | 30 | a short name for the bottom right quadrant, a word or two: what is both like the bottom end and like the right end (or empty, for none) |
| `top_left_things` | 50 | one or two familiar things that belong in the top left quadrant (both like the top end and like the left end), separated by \| (or empty, for none) |
| `top_right_things` | 50 | one or two familiar things that belong in the top right quadrant (both like the top end and like the right end), separated by \| (or empty, for none) |
| `bottom_left_things` | 50 | one or two familiar things that belong in the bottom left quadrant (both like the bottom end and like the left end), separated by \| (or empty, for none) |
| `bottom_right_things` | 50 | one or two familiar things that belong in the bottom right quadrant (both like the bottom end and like the right end), separated by \| (or empty, for none) |
| `dot` | 30 | the name of a dot in one of the quadrants: someone or something surprising there, the punchline |
| `dot_quadrant` | 12 | the quadrant the dot is in, the most surprising one for it: `top left`, `top right`, `bottom left`, `bottom right` (or empty, for any) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `2x2-matrix` | A 2×2 matrix about the concept along two odd axes, with one surprising dot as the punchline | the default; tags: diagram, matrix_diagram |

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
| `big-number` | A suspiciously precise statistic about the concept, as one big number | the default; images: `background` backdrop; tags: big_number |

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
| `kpi-tiles` | The concept's made-up key performance indicators, as on a corporate dashboard: figures that start out plausible, the last one the punchline | the default; images: `background` backdrop; tags: kpi |

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
| `quiz` | A quiz question about the concept for the audience: options that all seem possible, and a surprising answer | the default; tags: quiz |

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
| `social-media-post-crf` | A made-up social media post about the concept, by someone with strong opinions about it | the default; images: `photo` photo; tags: social_post |

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
| `news-headline-crf` | A made-up news story about the concept, as breaking news | the default; images: `photo` photo (or generated, from its prompt, with an image generator set up); tags: news |

## `agenda`

The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the agenda's title |
| `items` | 200 | three to five items, separated by \|, each at most 45 characters |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `agenda` | The talk's agenda: what it will cover | the default; `items`: three to five parts of the talk, in the order the slides after this one come, separated by \|; tags: agenda |

## `section`

A section's divider, opening a new part of the talk: its title, under its number (talkgenerator adds it).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 50 | the new section's title |
| `subtitle` | 90 | a line under it (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `section-divider` | A section's divider, opening the next part of the talk | the default; `title`: the title of the part of the talk that starts here, without a number (the slide has it); tags: section |

## `questions`

The closing slide, inviting the audience's questions: a question, a line under it (a last tip, say), and a picture to end on, if it has one (a funny one, or an earlier slide's, called back).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 30 | a question that invites the audience's questions |
| `subtitle` | 80 | a line under it (or empty, for none) |
| `callback` | 60 | the earlier slide whose picture this one shows again, as a callback: what that picture showed, as its image search query said it (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `questions` | The closing slide, inviting the audience's questions | the default; `subtitle`: a line under it, such as a disclaimer about the answers; images: `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: questions |

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
| `timeline` | The concept's made-up history, as a timeline whose last moment is the punchline | the default; tags: diagram, timeline |

## `pyramid`

A pyramid of three or four levels, from its top (the rarest, the punchline) down to its base; they appear one by one, a click each, from the base up.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the pyramid's title |
| `level_1` | 30 | the top of the pyramid: the punchline |
| `level_2` | 30 | the level under the top |
| `level_3` | 30 | the level under that (the base, if there's no fourth) |
| `level_4` | 30 | the base, under that (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `pyramid` | A hierarchy of needs about the concept, as a pyramid with something absurd at the top | the default; tags: diagram, pyramid |

## `funnel`

A funnel of three to five stages, from its widest at the top to its narrowest at the bottom, the punchline; they appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the funnel's title |
| `stage_1` | 30 | the widest stage, at the top |
| `stage_2` | 30 | the next stage, narrower |
| `stage_3` | 30 | the next stage (the narrowest, if there are no more) |
| `stage_4` | 30 | the next stage (or empty, for none) |
| `stage_5` | 30 | the narrowest stage, at the bottom (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `funnel` | A sales funnel about the concept, narrowing down to something absurd | the default; tags: diagram, funnel |

## `cycle`

A cycle of three to five steps around a circle, each leading to the next, and the last back to the first; they appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the cycle's title |
| `step_1` | 24 | the first step |
| `step_2` | 24 | the second step |
| `step_3` | 24 | the third step |
| `step_4` | 24 | a fourth step (or empty, for none) |
| `step_5` | 24 | a fifth step (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `cycle` | A vicious circle about the concept: steps that lead to each other, and back | the default; tags: cycle, diagram |

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
| `org-chart` | Who's really in charge of the concept, as an org chart with a surprising boss | the default; tags: diagram, org_chart |

## `iceberg`

An iceberg: what everyone sees, on its tip above the water, and two or three things under the water that nobody sees, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the iceberg's title |
| `tip` | 30 | what everyone sees, on the tip |
| `hidden_1` | 40 | something under the water that nobody sees |
| `hidden_2` | 40 | something else under the water |
| `hidden_3` | 40 | something deeper under the water (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `iceberg` | What lies beneath the concept: an iceberg whose tip everyone knows, and what's under the water | the default; tags: diagram, iceberg |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-crf` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` photo; tags: fun_fact |

## `acronym`

A made-up method, as an acronym: its letters down the slide, each with the word it stands for; the words appear one by one, a click each, the last one the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the method's title, which names the acronym |
| `acronym` | 6 | the acronym the words spell: their first letters in order, three to six capitals |
| `word_1` | 24 | the word the first letter stands for (one word for one letter) |
| `word_2` | 24 | the second letter's word |
| `word_3` | 24 | the third letter's word (the punchline, if it's the last) |
| `word_4` | 24 | the fourth letter's word (or empty, for none) |
| `word_5` | 24 | the fifth letter's word (or empty, for none) |
| `word_6` | 24 | the sixth letter's word (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `acronym` | A made-up method for the concept, as an acronym sold as the key to it all: its words get less plausible letter by letter, and the last one is the punchline | the default; tags: acronym |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 130 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 130 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `dare` | A dare, halfway through the talk | the default; tags: dare |

## `flowchart`

A flowchart that pretends to help decide: a yes-or-no question at the top, where each answer leads, and the end both lead to, the punchline; each appears on a click of its own (talkgenerator adds the Yes and the No).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `question` | 70 | the yes-or-no question at the top |
| `yes_step` | 48 | where Yes leads: a short step |
| `no_step` | 48 | where No leads: another short step |
| `end` | 48 | where both steps lead: the same end, the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `flowchart` | A flowchart that pretends to help decide something about the concept, but whatever the answer, it leads to the same absurd end | the default; tags: diagram, flowchart |

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
| `tier-list` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

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
| `wall-of-text` | An executive summary of the concept that nobody can read: a wall of dense jargon about it, with one absurd point hidden among the rest, which the presenter points at as if it were obvious | the default; tags: wall_of_text |

## `alignment_chart`

An alignment chart, as Dungeons & Dragons sorts characters: nine things in a grid of three by three, from lawful to chaotic across and from good to evil down (talkgenerator adds the axes' words), which appear one by one, a click each, in reading order: chaotic evil, the punchline, last.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the alignment chart's title |
| `lawful_good` | 60 | the lawful good one, in a few words |
| `neutral_good` | 60 | the neutral good one, in a few words |
| `chaotic_good` | 60 | the chaotic good one, in a few words |
| `lawful_neutral` | 60 | the lawful neutral one, in a few words |
| `true_neutral` | 60 | the true neutral one, in a few words |
| `chaotic_neutral` | 60 | the chaotic neutral one, in a few words |
| `lawful_evil` | 60 | the lawful evil one, in a few words |
| `neutral_evil` | 60 | the neutral evil one, in a few words |
| `chaotic_evil` | 60 | the chaotic evil one, in a few words: the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `alignment-chart` | An alignment chart of things to do with the concept, as Dungeons & Dragons sorts characters: harmless and wholesome as lawful good, unhinged as chaotic evil, the punchline | the default; tags: alignment_chart |

## `red_flags`

Red flags: three to five warning signs, each beside a red flag, appearing one by one, a click each, each more alarming than the last: the last one is the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title, which says these are red flags (of what) |
| `flag_1` | 90 | the first red flag |
| `flag_2` | 90 | the second red flag |
| `flag_3` | 90 | the third red flag (the punchline, if it's the last) |
| `flag_4` | 90 | a fourth red flag (or empty, for none) |
| `flag_5` | 90 | a fifth red flag (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `red-flags` | Red flags about the concept, as in dating advice: warning signs that someone or something around it is trouble, each more alarming than the last | the default; tags: red_flags |

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
| `reviews` | Made-up customer reviews of the concept, as if it were a product: glowing ones that take it far too seriously, then a one-star review, the punchline | the default; tags: reviews |

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
| `error-message` | A fake error message about the concept, as if the talk itself just crashed: a dialog with a playful, absurd message about the concept, worded as computers word them, and buttons, the last one the punchline | the default; tags: error_message |

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
| `problem` | The problem the talk is about, early on, as a TED speaker opens with one to hook the audience: a problem with the concept that the talk's thesis will answer | the default; `kicker`: a short heading over the problem, as a TED speaker would open with it, such as 'Picture this' or 'Sound familiar?'; images: `background` calm-backdrop or backdrop, `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: problem_slide |

## `exhibit`

Exhibit A: one odd picture, as the evidence in a case, with an evidence tag beside it or a marker on it (talkgenerator adds 'Exhibit A' and a case number; a later exhibit in the talk is Exhibit B, of the same case), and a short note on the tag, if it has one: the presenter explains what it proves.

| Text | At most | What to write |
| --- | --- | --- |
| `note` | 40 | a few words on the evidence tag about the picture, as a police report notes where or when it was found (or empty, for none) |

Images: `picture`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `exhibit-a-crf` | Exhibit A: an odd picture to do with the concept, as the evidence in a case, for the presenter to explain what it proves | the default; `picture_query`: an image search query for the odd picture that is the evidence: something concrete and surprising that the case could hinge on, in two to six plain English words; images: `picture` weird-stock (or generated, from its prompt, with an image generator set up); tags: exhibit |

## `pick_one`

Pick one: two pictures side by side, without captions, with 'OR' between them, under 'Pick one:' (talkgenerator adds both, unless the slide has a heading of its own): the audience picks, and the presenter explains.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | a heading of the slide's own over the two pictures, that asks the audience to choose, in a few words (or empty, for none) |

Images: `picture_1`, `picture_2`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `pick-one-crf` | Two pictures to pick one of, without captions: two things to do with the concept that are absurdly hard to choose between, for the audience to vote on and the presenter to explain | the default; `picture_1_query`: an image search query for the first thing to pick: something concrete, in two to six plain English words; `picture_2_query`: an image search query for the second thing to pick: something just as concrete, but absurdly different from the first, in two to six plain English words; images: `picture_1` weird-stock, `picture_2` weird-stock; tags: pick_one |

## `equation`

A picture equation, as story cubes tell a story: a thing plus another thing equals a third, the punchline, which appears on a click; each thing a picture, or else an emoji (talkgenerator adds the + and the =): the presenter explains how it adds up.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | a title over the equation, in a few words (or empty, for none) |
| `term_1` | 16 | a single emoji for the first thing |
| `term_2` | 16 | a single emoji for the second thing, which is added to the first |
| `result` | 16 | a single emoji for what the two make together: the surprising punchline |

Images: `term_1_picture`, `term_2_picture`, `result_picture`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `picture-equation-crf` | A picture equation about the concept, as story cubes tell a story: something to do with it plus something else equals a surprise, for the presenter to explain how it adds up | the default; `term_1_picture_query`: an image search query for a photo of the first thing, in one to four plain English words; `term_2_picture_query`: an image search query for a photo of the second thing, in one to four plain English words; `result_picture_query`: an image search query for a picture of what the two make together, the surprise, in two to six plain English words; images: `term_1_picture` photo, `term_2_picture` photo, `result_picture` weird-stock; tags: equation |

## `what_do_you_see`

What do you see?: a picture of a face in something that has none (pareidolia), or without one, an inkblot that talkgenerator draws, as a Rorschach test has them, under the question 'What do you see?' (talkgenerator adds it, unless the slide has a question of its own): the presenter explains what everyone should see in it.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 40 | a question of the slide's own over the picture, that asks the audience what they see in it, in a few words (or empty, for none) |

Images: `picture`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `what-do-you-see-crf` | An inkblot that talkgenerator draws, as a Rorschach test has them, for the audience to say what they see in it and the presenter to explain what everyone should see | the default; shows no `picture`; tags: what_do_you_see |

## `before_after`

Before and after: two pictures that have nothing to do with each other, as a transformation, under 'Before' and 'After' (talkgenerator adds them), with an arrow between them, the after on a click: the presenter explains how the one became the other.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | a title of the slide's own, in a few words (or empty, for none) |

Images: `before_picture`, `after_picture`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `before-and-after-crf` | A before and after about the concept: two pictures that have nothing to do with each other, as a transformation, for the presenter to explain how the one became the other | the default; `before_picture_query`: an image search query for the 'before' picture, of something to do with the concept, in two to six plain English words; `after_picture_query`: an image search query for the 'after' picture: something that has nothing to do with the first, as if the first became it, in two to six plain English words; images: `before_picture` photo, `after_picture` weird-stock; tags: before_after |
