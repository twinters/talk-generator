# The slides of an `academic` talk

A talk at an academic conference, with affiliations on its title slide: the motivation (the problem the research is about), the outline, related work, the method, the results (with p-values), the limitations, future work, the acknowledgements and the references, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format academic`.

A plan's `title` is like a paper's title at a conference: a catchy phrase, a colon and a dry subtitle, and its `presenter_job` is an affiliation, as on a paper, in a few words: their position and a made-up university or department.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `motivation` | 1 | `motivation-academic`, `research-question-academic` |
| `outline` | 1 | `outline-academic` |
| `related_work` | 1 | `related-work-matrix-academic`, `related-work-timeline-academic`, `related-work-venn-academic` |
| `method` | 1 to 2 | `equation-academic`, `experimental-setup-academic`, `method-academic` |
| `results` | 1 to 3 | `p-value-academic`, `results-correlation-academic`, `results-over-time-academic`, `results-ranking-academic` |
| `limitations` | 1 | `limitations-academic`, `limitations-statement-academic` |
| `future_work` | 1 | `future-work-academic`, `future-work-flowchart-academic`, `research-cycle-academic` |
| `acknowledgements` | 1 | `acknowledgements-academic`, `acknowledgements-list-academic` |
| `references` | 1 | `references-academic`, `references-figure-academic` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `experimental-setup-academic` | The experimental setup, as one photo of an odd contraption, under a title | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Experimental setup'; images: `image` weird-stock (or generated, from its prompt, with an image generator set up); tags: method, single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `reddit-chart-academic` | A real chart from the internet, filling the slide | the default; `title`: a confident conclusion about the concept that the chart supposedly proves, as if it were obvious (the chart is a real one, about something else entirely); images: `image` bad-charts; tags: chart |
| `full-screen-gif-academic` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `provocation-academic` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a researcher puts them on a slide, dryly, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 90 | the big text over the photo: one short sentence |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `research-question-academic` | The talk's motivation, right after the title: its research question, big over a photo | the default; `text`: the research question about the concept, as one short question, in twelve words at most; images: `background` calm-backdrop or backdrop; tags: motivation, research_question, statement |
| `equation-academic` | The method's key equation, big over a photo: one line in letters and symbols, with the concept in it, that sums up the method | `text`: the equation, written out in plain characters (such as x² and ×), on one line; images: `background` calm-backdrop or backdrop; tags: equation, method, statement |
| `limitations-statement-academic` | The study's main limitation, admitted in one short sentence over a photo, as if it were minor | `text`: the limitation, admitted as if it were minor, in ten words at most; images: `background` calm-backdrop or backdrop; tags: limitations, statement |
| `quote-academic` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |
| `full-screen-pixabay-deep-academic` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |
| `wikihow-bold-statement-academic` | A bold statement over a photo | `text`: a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'; images: `background` calm-backdrop or backdrop; tags: bold_statement, statement |

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
| `two-captions-weird-reddit-academic` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; images: `image_1` weird, `image_2` meme-chaos; tags: multi_caption, reddit, two_captions |

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
| `acknowledgements-academic` | The acknowledgements: three who made the work possible (made up, or a funder, a lab animal, a coffee machine), each a photo with a caption | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Acknowledgements'; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: acknowledgements, three_captions |

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
| `results-correlation-academic` | The results, as a scatter plot of a made-up correlation about the concept, with its r and its p-value in the title | the default; `title`: the correlation found, as a claim, with its r and with a suspicious p-value, just under 0.05; tags: chart, curve, results |

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
| `results-over-time-academic` | The results over time: this work's method as one line, and a baseline as a second line that appears on a click, as the punchline | the default; `title`: the chart's claim, with a suspicious p-value, just under 0.05; `line`: this work's method, by its made-up name; `second_line`: a baseline or an earlier method; tags: chart, results, trend_chart |

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
| `results-ranking-academic` | The results, as a bar chart of the methods compared: baselines and earlier methods, and this work's method last, winning by far | the default; `title`: what the bars compare, with a suspicious p-value, just under 0.05; `bars`: three to five baselines and earlier methods (only their names), separated by \|, and this work's method's made-up name last; `value_axis`: the measure, with its unit; tags: bar_chart, chart, results |

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
| `related-work-venn-academic` | Related work, as a Venn diagram: two or three fields of research that seem to have nothing in common, and this work where they overlap, the punchline | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Related work'; `overlap`: this work, the punchline; tags: related_work, venn_diagram |

## `matrix`

A 2×2 matrix: two axes of everyday opposites that cross in the middle, with a word or two at each end, a short name in each quadrant (or familiar things as dots where they belong, or neither), and one dot with a name, the punchline, which appears on a click.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the matrix's title |
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
| `related-work-matrix-academic` | Related work, as a 2×2 matrix: earlier work in three of its quadrants (made-up authors, as 'et al.' with a year), and this work's method as the dot, alone in the last one | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Related work'; `x_left`: the end of the axis along the bottom where earlier work is; `x_right`: its other end, the opposite, where this work is; `y_bottom`: the end of the axis going up where earlier work is; `y_top`: its other end, the opposite, where this work is; `top_left`: an earlier work, as a made-up author 'et al.' and a year in brackets; `bottom_left`: an earlier work, as a made-up author 'et al.' and a year in brackets; `bottom_right`: an earlier work, as a made-up author 'et al.' and a year in brackets; `top_right`: the label of the quadrant where only this work is, such as the gap it fills; `dot`: this work's method, by its made-up name; `dot_quadrant`: top right; tags: matrix_diagram, related_work |

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
| `p-value-academic` | The result that matters, as one p-value: a big number just under the threshold, what it shows, and where in the paper it is | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Main result'; `number`: the p-value, just under 0.05, such as 'p = 0.049'; `label`: what it shows, and what it took to get it, without the number itself; `source`: where in the paper it is, such as an appendix; images: `background` backdrop; tags: big_number, results |

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
| `quiz-academic` | A quiz question about the concept for the audience: options that all seem possible, and a surprising answer | the default; tags: quiz |

## `agenda`

The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the agenda's title |
| `items` | 150 | three to five items, separated by \|, each at most 36 characters |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `outline-academic` | The talk's outline, as a conference talk has it: the parts it goes through, in order | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Outline'; `items`: three to five parts of the talk, in the order they come, separated by \|, each at most 36 characters; tags: agenda, outline |
| `acknowledgements-list-academic` | The acknowledgements, as a list of who and what made the work possible (made up, never real people) | `title`: the slide's title, as a conference talk's slide has it, such as 'Acknowledgements'; `items`: three to five who or what to thank, each in a few words, separated by \|, each at most 36 characters; tags: acknowledgements |

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
| `related-work-timeline-academic` | Related work, as the field's made-up history: what earlier research found, oldest first, and this work last, the punchline | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'A brief history of the field'; tags: related_work, timeline |
| `future-work-academic` | Future work, as a timeline of what comes next, soonest first, the last moment the punchline | `title`: the slide's title, as a conference talk's slide has it, such as 'Future work'; `event_1`: what comes then, in two to four words; `event_2`: what comes then, in two to four words; `event_3`: what comes then, in two to four words; `event_4`: what comes then, in two to four words; `event_5`: what comes then, in two to four words; tags: future_work, timeline |

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
| `research-cycle-academic` | Future work, as the research cycle: three to five steps of academic life, each leading to the next, and the last back to the first | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Future work'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: cycle, future_work |

## `iceberg`

An iceberg: what everyone sees, on its tip above the water, and two or three things under the water that nobody sees, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the iceberg's title |
| `tip` | 30 | what everyone sees, on the tip |
| `hidden_1` | 40 | something under the water that nobody sees |
| `hidden_2` | 40 | something else under the water |
| `hidden_3` | 40 | something deeper under the water (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `limitations-academic` | The study's limitations, as an iceberg: the small one everyone sees, on its tip, and the ones under the water that sink the study | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Limitations'; tags: iceberg, limitations |

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
| `method-academic` | The method, as a diagram of three to five steps, each leading to the next, the last one the punchline (a step that can't be right, say) | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'Method'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: method, process |

## `references`

A talk's references, as an academic talk ends with them: three to five made-up works it cites, which the slide numbers itself ([1], [2]...) and which appear one by one, a click each; and a picture of one of them, if it has one (a book's cover, or a figure from a paper), with a caption that says which, on the click after them.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the slide's title |
| `items` | 260 | three to five made-up works the talk cites, separated by \|, each at most 36 characters, without a number in front |
| `caption` | 30 | which of the works the picture is of, by its number in the list, such as 'Cover of [2]' (or empty, for none) |

Images: `figure`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `references-academic` | The references: three to five made-up works that the talk cites, in a citation style | the default; `title`: the slide's title, as a conference talk's slide has it, such as 'References'; `items`: three to five short made-up references, each an author 'et al.', a year in brackets and a journal of two or three words (no paper's title), without a number in front (the slide numbers them), separated by \|, each at most 36 characters; `caption`: which work it's the cover of, by its number in the list, such as 'Cover of [2]'; images: `figure` book-covers, else museum, else illustration (or generated, from its prompt, with an image generator set up); tags: references |
| `references-figure-academic` | The references: three to five made-up works that the talk cites, in a citation style | `title`: the slide's title, as a conference talk's slide has it, such as 'References'; `items`: three to five short made-up references, each an author 'et al.', a year in brackets and a journal of two or three words (no paper's title), without a number in front (the slide numbers them), separated by \|, each at most 36 characters; `caption`: which work the figure is from, by its number in the list, such as '[3], Fig. 2'; images: `figure` bad-charts, else museum, else illustration; tags: references |

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
| `meme-academic` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 100 | the fact: one short sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-academic` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

## `flowchart`

A flowchart that pretends to help decide: a yes-or-no question at the top, where each answer leads, and the end both lead to, the punchline; each appears on a click of its own (talkgenerator adds the Yes and the No).

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 45 | the slide's title (or empty, for none) |
| `question` | 50 | the yes-or-no question at the top |
| `yes_step` | 48 | where Yes leads: a short step |
| `no_step` | 48 | where No leads: another short step |
| `end` | 48 | where both steps lead: the same end, the punchline |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `future-work-flowchart-academic` | Future work, as a flowchart that pretends to decide what comes next, whose every answer leads to more research | the default; tags: flowchart, future_work |

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
| `motivation-academic` | The talk's motivation, right after the title, to hook the audience: the problem the research is about, as a conference talk states it, played straight however absurd | the default; `kicker`: a short heading over the problem, as a conference talk has it, such as 'Motivation' or 'The problem'; `detail`: a short line under it, a few words, that makes it hit home, dryly: how often it happens, to whom, or what science doesn't know about it; it appears on a click; images: `background` calm-backdrop or backdrop, `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: motivation, problem_slide |
