# The slides of a `ted` talk

A TED-like talk with copyright-free images only (stock photos, artworks and old photos), for decks shown in public; it has no full-screen images, gifs or memes, and no recipes for slides about the presenter.

Every talk starts with a title slide, made from the plan's `title` and `presenter_job` (talkgenerator adds the presenter's name). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe.

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
| `two-captions-copyright-free` | Two captioned images that contrast or compare, like 'Expectation' and 'Reality' | the default; tags: multi_caption, two_captions |
| `2-conclusions-crf` | The talk's conclusions | `title`: a title such as 'Conclusions' or 'What we learned'; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |

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
| `3-conclusions-crf` | The talk's conclusions | `title`: a title such as 'Conclusions' or 'What we learned'; `caption_1`: a lesson from the talk, calling back to an earlier slide; `caption_2`: a lesson from the talk, calling back to an earlier slide; `caption_3`: a lesson from the talk, calling back to an earlier slide; tags: conclusion |

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
| `funny_answer` | 30 | a third answer, besides yes and no, such as 'Only on Tuesdays' |

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

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `correlation-curve` | A made-up scientific finding about the concept | the default; tags: chart, curve |
