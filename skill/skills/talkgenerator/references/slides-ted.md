# The slides of a `ted` talk

A TED-like talk with copyright-free images only (stock photos, artworks and old photos), for decks shown in public; it has no full-screen images, gifs or memes, and no recipes for slides about the presenter.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe.

Made by `talkgenerator formats --details --format ted`.

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `single-image-copyright-free` | A photo with a title | the default; tags: single_image |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-pixabay-deep` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; tags: deep, full_image |
| `full-screen-pixabay-quote` | A real quote over a photo (talkgenerator finds the quote, about the concept) | finds its `text` itself (don't write one); tags: full_image, quote |
| `wikihow-bold-statement-crf` | A bold statement over a photo | the default; `text`: a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'; tags: bold_statement, statement |
| `quote-crf` | A real quote over a photo (talkgenerator finds the quote, about the concept) | finds its `text` itself (don't write one); tags: quote, statement |
| `anecdote-crf` | A personal anecdote the presenter now has to tell | `text`: the title of the anecdote, such as 'The time I ...'; tags: anecdote |

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
| `two-history-pictures-crf` | Two old photos from the history of the slide's concept | `title`: a title about the concept's history; `caption_1`: a moment from long ago; `caption_2`: a later moment; tags: history, two_images |
| `two-captions-copyright-free` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; tags: multi_caption, two_captions |
| `2-conclusions-crf` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |

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
| `three-captions-weird-crf` | Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan | the default; tags: multi_caption, three_captions |
| `3-conclusions-crf` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; `caption_3`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |

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
| `historical-figure-quote-crf` | What a made-up historical figure once said about the slide's concept | the default; tags: history, quote |

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

A scatter plot of made-up data, under a claim of a correlation.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 90 | a made-up correlation between two things, as a claim |
| `x_axis` | 40 | the axis along the bottom: the first of the two things (or empty, for none) |
| `y_axis` | 40 | the axis going up: the second thing (or empty, for none) |
| `outlier` | 30 | one point far above the others, named after someone or something that doesn't belong there (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `correlation-curve` | A made-up scientific finding about the concept | the default; tags: chart, curve |

## `chart_trend`

A line chart of a made-up trend along two odd axes; a second line, if any, draws itself across it on a click, as the punchline.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 90 | the chart's claim, as its title |
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

A 2×2 matrix: two axes that cross in the middle, with a title at each end, a label in each quadrant, and one dot with a name, the punchline, which appears on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the matrix's title |
| `x_left` | 30 | the title at the left end of the axis along the bottom |
| `x_right` | 30 | the title at the right end of that axis: the opposite of the left end |
| `y_bottom` | 30 | the title at the bottom end of the axis going up |
| `y_top` | 30 | the title at the top end of that axis: the opposite of the bottom end |
| `top_left` | 30 | the label of the top left quadrant: what is both like the top end and like the left end |
| `top_right` | 30 | the label of the top right quadrant: what is both like the top end and like the right end |
| `bottom_left` | 30 | the label of the bottom left quadrant: what is both like the bottom end and like the left end |
| `bottom_right` | 30 | the label of the bottom right quadrant: what is both like the bottom end and like the right end |
| `dot` | 30 | the name of a dot in one of the quadrants: someone or something surprising there, the punchline |
| `dot_quadrant` | 12 | the quadrant the dot is in, the most surprising one for it: `top left`, `top right`, `bottom left`, `bottom right` (or empty, for any) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `2x2-matrix` | A 2×2 matrix about the concept along two odd axes, with one surprising dot as the punchline | the default; tags: diagram, matrix_diagram |

## `big_number`

A big, made-up number, with what it counts under it: a figure the presenter has to explain.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |
| `number` | 12 | the big number, with its unit if it has one: a percentage, an amount or a count |
| `label` | 90 | what the number counts or measures, in a few words |
| `source` | 60 | a made-up, unreliable source for the number (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `big-number` | A suspiciously precise statistic about the concept, as one big number | the default; tags: big_number |

## `kpi`

Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; the last one, the punchline, appears on a click.

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

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `kpi-tiles` | The concept's made-up key performance indicators, as on a corporate dashboard: figures that start out plausible, the last one the punchline | the default; tags: kpi |

## `quiz`

A quiz question for the audience, with three or four options (A to D); the answer, and why, appear on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 90 | the quiz question |
| `option_a` | 40 | option A |
| `option_b` | 40 | option B |
| `option_c` | 40 | option C |
| `option_d` | 40 | option D (or empty, for none) |
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
| `social-media-post-crf` | A made-up social media post about the concept, by someone with strong opinions about it | the default; tags: social_post |

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
| `news-headline-crf` | A made-up news story about the concept, as breaking news | the default; tags: news |

## `agenda`

The talk's agenda: three to five items it will cover, numbered.

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
| `section-divider` | A section's divider, opening the next part of the talk | the default; `title`: the title of the part of the talk that starts here; tags: section |

## `questions`

The closing slide, inviting the audience's questions.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 30 | a question that invites the audience's questions |
| `subtitle` | 80 | a line under it (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `questions` | The closing slide, inviting the audience's questions | the default; `subtitle`: a line under it, such as a disclaimer about the answers; tags: questions |
