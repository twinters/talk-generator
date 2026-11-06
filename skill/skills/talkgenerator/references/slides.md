# The slides of a `default` talk

A TED-like talk: about the presenter, history, bold statements, captioned images, charts and conclusions, with images from every source (memes and gifs too).

Every talk starts with a title slide, made from the plan's `title` and `presenter_job` (talkgenerator adds the presenter's name). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe.

Made by `talkgenerator formats --details --format default`.

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `weird-hobby` | The presenter's weird hobby | `title`: the presenter's weird hobby; tags: about_me |
| `single-image-gif` | A gif with a title | tags: gif, single_image |
| `inspirobot` | An inspirational poster (made by InspiroBot) that the presenter has to explain | `title`: a title such as 'Something my father always told me'; needs no `image_query`; tags: inspiration, statement |
| `single-image-copyright-free` | A photo with a title | the default; tags: single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-gif` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; tags: full_image, gif |
| `full-screen-meme` | A meme, filling the slide | shows no `title`; tags: full_image, meme |
| `full-screen-neutral-images` | A photo, filling the slide | the default; tags: full_image, neutral |
| `reddit-chart` | A chart, filling the slide | shows no `title`; tags: chart |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `wikihow-bold-statement` | A bold statement over a photo | the default; `text`: a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'; tags: bold_statement, statement |
| `quote` | A real quote over a photo (talkgenerator finds the quote, about the concept) | finds its `text` itself (don't write one); tags: quote, statement |
| `anecdote` | A personal anecdote the presenter now has to tell | `text`: the title of the anecdote, such as 'The time I ...'; tags: anecdote |

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
| `about-me-location-job` | About the presenter: where they come from and their job | `title`: a title such as 'About me' or 'Who am I?'; `caption_1`: where the presenter comes from: a country, a city or a place; `caption_2`: the presenter's (possibly made-up) job; tags: about_me |
| `two-history-pictures` | Two old photos from the history of the slide's concept | `title`: a title about the concept's history; `caption_1`: a moment from long ago; `caption_2`: a later moment; tags: history, two_images |
| `two-captions-gifs` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | tags: gif, multi_caption, two_captions |
| `two-captions-weird-reddit` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | tags: multi_caption, reddit, two_captions |
| `two-captions-weird` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | tags: multi_caption, reddit, two_captions |
| `2-conclusions` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |
| `two-captions-copyright-free` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; tags: multi_caption, two_captions |

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
| `about-me-location-job-weirdhobby` | About the presenter: where they come from, their job and their weird hobby | `title`: a title such as 'About me' or 'Who am I?'; `caption_1`: where the presenter comes from: a country, a city or a place; `caption_2`: the presenter's (possibly made-up) job; `caption_3`: the presenter's weird hobby; tags: about_me |
| `about-me-location-book-weirdhobby` | About the presenter: where they come from, the book they wrote, and their weird hobby | `title`: a title such as 'About me' or 'Who am I?'; `caption_1`: where the presenter comes from: a country, a city or a place; `caption_2`: the title of a book the presenter wrote; `caption_3`: the presenter's weird hobby; tags: about_me |
| `three-captions-weird` | Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan | tags: multi_caption, reddit, three_captions |
| `3-conclusions` | The talk's conclusions | `title`: a title for the conclusions, in a few words of your own; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; `caption_3`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |
| `three-captions-weird-crf` | Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan | the default; tags: multi_caption, three_captions |

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
| `historical-figure-quote` | What a made-up historical figure once said about the slide's concept | tags: history, quote |
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
