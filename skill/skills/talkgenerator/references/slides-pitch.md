# The slides of a `pitch` talk

A startup pitch to investors: the problem, the solution, the market (TAM, SAM and SOM), the business model, the traction, the competition, the team, the roadmap and the ask, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format pitch`.

A plan's `title` is like a startup pitch's title: the startup's made-up name and its one-line promise, and its `presenter_job` is their role at the startup they pitch, with the startup's made-up name.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `problem` | 1 to 2 | `problem-number-pitch`, `problem-statement-pitch` |
| `solution` | 1 to 2 | `before-and-after-pitch`, `how-it-works-pitch`, `solution-pitch` |
| `market` | 1 | `market-number-pitch`, `market-size-pitch` |
| `business_model` | 1 | `flywheel-pitch`, `pricing-pitch`, `revenue-streams-pitch` |
| `traction` | 1 to 2 | `hockey-stick-pitch`, `testimonial-pitch`, `traction-figures-pitch` |
| `competition` | 1 | `competition-matrix-pitch`, `competition-ranking-pitch` |
| `team` | 1 | `team-org-chart-pitch`, `team-pitch` |
| `roadmap` | 1 | `roadmap-pitch` |
| `ask` | 1 | `the-ask-pitch` |
| `closing` | 1 | `closing-pitch` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `solution-pitch` | The startup's solution: its product, in one photo, under a title that introduces it by name | the default; `title`: a title that introduces the product by the startup's made-up name; images: `image` photo (or generated, from its prompt, with an image generator set up); tags: single_image, solution |
| `inspirobot-pitch` | An inspirational poster (made by InspiroBot) that the presenter has to explain | `title`: a title such as 'Something my father always told me'; images: `image` inspirobot; needs no `image_query`; tags: inspiration, statement |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-gif-pitch` | A gif, filling the slide | the default; `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `full-screen-neutral-images-pitch` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `problem-statement-pitch` | The problem the startup solves, as a bold statement over a photo: a pain that everyone supposedly has with the concept | the default; `text`: the problem, as one bold sentence or question, stated as a crisis; images: `background` calm-backdrop; tags: problem, statement |
| `wikihow-bold-statement-pitch` | A bold statement over a photo | `text`: a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'; images: `background` calm-backdrop; tags: bold_statement, statement |
| `anecdote-pitch` | A personal anecdote the presenter now has to tell | `text`: the title of the anecdote, such as 'The time I ...'; images: `background` calm-backdrop; tags: anecdote |

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
| `before-and-after-pitch` | Life before the startup's product and after it, as two captioned photos | the default; `caption_1`: life before the product, in a few words; `caption_2`: life after it; images: `image_1` photo, `image_2` weird-stock; tags: solution, two_captions |
| `two-captions-gifs-pitch` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | images: `image_2` gifs, else weird; tags: gif, multi_caption, two_captions |

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
| `team-pitch` | The startup's team: three photos of people (never real ones), each with a made-up role | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'The team'; `caption_1`: a team member's made-up role, as a pitch deck says it; `caption_2`: a team member's made-up role, as a pitch deck says it; `caption_3`: a team member's made-up role, as a pitch deck says it: the punchline; images: `image_1` portrait, `image_2` portrait, `image_3` portrait; tags: team, three_captions |

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

## `chart_categories`

A pie chart of made-up shares.

| Text | At most | What to write |
| --- | --- | --- |
| `question` | 90 | the question the pie chart answers, as its title |
| `categories` | 120 | two to five answers, separated by \| |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `revenue-streams-pitch` | Where the startup's money comes from, as a pie chart of its revenue streams, one of them absurd | the default; `question`: the chart's title, such as 'Our revenue streams'; `categories`: three to five revenue streams, separated by \|; tags: business_model, chart, pie_chart |

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
| `hockey-stick-pitch` | The startup's traction: one line that grows like a hockey stick, with the moment it took off | the default; `title`: the chart's claim about the startup's growth; `shape`: how the line goes: hockey stick, or exponential; `line`: the startup's made-up name; `event`: the moment it took off, marked on the line; shows no `second_line`; shows no `second_shape`; tags: chart, traction, trend_chart |

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
| `competition-ranking-pitch` | Why the startup wins: a ranking of its competitors (made up, or old ways of doing things), which the startup, the last bar, wins by far | the default; `title`: what the ranking compares, as its title; `bars`: three to five competitors (only their names), separated by \|, and the startup's made-up name last; tags: bar_chart, chart, competition |

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
| `competition-matrix-pitch` | The competition, as a 2×2 matrix: the competitors (made up, or old ways of doing things) in three of its quadrants, and the startup as the dot, alone in the best one | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'Competition'; `x_left`: the bad end of the axis along the bottom; `x_right`: its good end, the opposite of the bad one; `y_bottom`: the bad end of the axis going up; `y_top`: its good end, the opposite of the bad one; `top_left`: a competitor (made up, or an old way of doing it), by its name; `bottom_left`: a competitor (made up, or an old way of doing it), by its name; `bottom_right`: a competitor (made up, or an old way of doing it), by its name; `top_right`: the label of the quadrant that's best on both axes, where only the startup is; `dot`: the startup, by its made-up name; `dot_quadrant`: top right, the quadrant that's best on both axes; tags: competition, matrix_diagram |

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
| `problem-number-pitch` | The problem the startup solves, as one alarming, suspiciously precise statistic about the concept | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'The problem'; `number`: the number as people read it, with its unit or currency, such as '3.7 billion' or '$2M'; `label`: what the number counts, without the number itself; tags: big_number, problem |
| `market-number-pitch` | The market's size, as one enormous amount of money that the concept is supposedly worth | `title`: the slide's title, as a pitch deck's slide has it, such as 'Market size'; `number`: the market's size, in money; `label`: what the number counts, without the number itself; tags: big_number, market |
| `the-ask-pitch` | The ask: how much money the startup is raising, and what for | `title`: the slide's title, as a pitch deck's slide has it, such as 'The ask'; `number`: the amount the startup raises, with its currency, such as '$2M'; `label`: what the money is for, or how much of the startup it buys; `source`: the round and its terms, as a pitch deck says them; tags: ask |

## `kpi`

Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; they appear one by one, a click each, the last one the punchline.

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
| `pricing-pitch` | The business model, as pricing plans on tiles: each plan a price and what it gets you, from free to the last one, the punchline | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'Business model'; `number_1`: the plan's price; `number_2`: the plan's price; `number_3`: the plan's price; `number_4`: the plan's price; `label_1`: the plan's name and what it gets you; `label_2`: the plan's name and what it gets you; `label_3`: the plan's name and what it gets you; `label_4`: the plan's name and what it gets you; tags: business_model, kpi |
| `traction-figures-pitch` | The startup's traction, as figures on tiles: growth that starts out impressive, the last figure the punchline (such as its revenue) | `title`: the slide's title, as a pitch deck's slide has it, such as 'Traction'; tags: kpi, traction |

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
| `testimonial-pitch` | A happy customer's post about the startup, as a testimonial: too happy, or happy about the wrong thing | the default; `title`: a title such as 'What our users say', or empty for none; images: `photo` photo; tags: social_post, traction |

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
| `news-headline-pitch` | A made-up news story about the concept, as breaking news | the default; images: `photo` neutral (or generated, from its prompt, with an image generator set up); tags: news |

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
| `closing-pitch` | The closing slide, after the ask: inviting the investors' questions (and their money) | the default; `subtitle`: a line under it, about investing; images: `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: closing, questions |

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
| `roadmap-pitch` | The startup's roadmap: what it will do when, soonest first, the last moment the punchline | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'Roadmap'; `event_1`: what the startup does then, in a few words; `event_2`: what the startup does then, in a few words; `event_3`: what the startup does then, in a few words; `event_4`: what the startup does then, in a few words; `event_5`: what the startup does then, in a few words; tags: roadmap, timeline |

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
| `market-size-pitch` | The market's size, as a funnel: the total addressable market (TAM) at the top, the serviceable market (SAM), and the market the startup will win (SOM) at the bottom, the punchline | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'Market size'; `stage_1`: TAM, an amount and who's in it; `stage_2`: SAM, an amount and who's in it; `stage_3`: SOM, an amount and who's in it: the punchline; shows no `stage_4`; shows no `stage_5`; tags: funnel, market |

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
| `flywheel-pitch` | The business model, as a flywheel: three to five things that feed each other, and the last back into the first | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'Our flywheel'; `step_1`: a thing that feeds the next, in two to four words; `step_2`: a thing that feeds the next, in two to four words; `step_3`: a thing that feeds the next, in two to four words; `step_4`: a thing that feeds the next, in two to four words; `step_5`: a thing that feeds the next, in two to four words; tags: business_model, cycle |

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
| `team-org-chart-pitch` | The startup's team, as an org chart: its roles, under who's really in charge, the punchline | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'The team'; `boss`: who's really in charge, in a few words: the punchline; `report_1`: a role on the team, in a few words (without a name); `report_2`: a role on the team, in a few words (without a name); `report_3`: a role on the team, in a few words (without a name); `report_4`: a role on the team, in a few words (without a name); tags: org_chart, team |

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
| `how-it-works-pitch` | How the product works, in three to five steps, the last one the punchline: a step that gives the game away, or one nobody can explain | the default; `title`: the slide's title, as a pitch deck's slide has it, such as 'How it works'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: process, solution |

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
| `meme-pitch` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-pitch` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; tags: fun_fact |

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
| `acronym-pitch` | A made-up method for the concept, as an acronym sold as the key to it all: its words get less plausible letter by letter, and the last one is the punchline | the default; tags: acronym |
