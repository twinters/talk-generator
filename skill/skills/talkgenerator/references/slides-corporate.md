# The slides of a `corporate` talk

A company's all-hands meeting or quarterly business review: the agenda, the KPIs against their targets, the quarter's wins, the roadmap, an org change, the synergies, the ask of everyone and Q&A, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format corporate`.

A plan's `title` is like an all-hands' or a quarterly business review's title: the quarter, and a corporate slogan for it, and its `presenter_job` is their position at the company, as its org chart says it, with the company's made-up name.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `agenda` | 1 | `agenda-corporate`, `executive-summary-corporate` |
| `kpis` | 1 to 2 | `actual-vs-target-corporate`, `headline-number-corporate`, `kpi-dashboard-corporate`, `results-by-region-corporate`, `sales-pipeline-corporate` |
| `wins` | 1 to 2 | `ceo-s-post-corporate`, `customer-reviews-corporate`, `wins-of-the-quarter-corporate` |
| `roadmap` | 1 | `new-process-corporate`, `planning-cycle-corporate`, `roadmap-corporate` |
| `org_change` | 1 | `before-and-after-the-reorganisation-corporate`, `new-hierarchy-corporate`, `new-structure-corporate` |
| `synergies` | 1 | `priority-matrix-corporate`, `synergies-corporate` |
| `ask` | 1 | `the-ask-corporate`, `the-ask-in-numbers-corporate` |
| `qa` | 1 | `q-a-corporate` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `inspirobot-corporate` | An inspirational poster (made by InspiroBot) that the presenter has to explain | the default; `title`: a title such as 'Something my father always told me'; images: `image` inspirobot; needs no `image_query`; tags: inspiration, statement |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `full-screen-neutral-images-corporate` | A photo, filling the slide | the default; images: `image` neutral; tags: full_image, neutral |
| `provocation-corporate` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, in corporate jargon, as leadership says them, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-ask-corporate` | The ask: what leadership needs from everyone, as one bold sentence over a photo, impossible and cheerful | the default; `text`: the ask, as one bold sentence, said to everyone; images: `background` calm-backdrop or backdrop; tags: ask |
| `quote-corporate` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: quote, statement |
| `full-screen-pixabay-quote-corporate` | A real quote over a photo (talkgenerator finds the quote, about the concept) | images: `background` calm-backdrop or backdrop; finds its `text` itself (don't write one); tags: full_image, quote |

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
| `before-and-after-the-reorganisation-corporate` | The company before its reorganisation and after it, as two captioned photos: how little changed | the default; `caption_1`: the company before, in a few words; `caption_2`: the company after; images: `image_1` corporate-stock, else photo, `image_2` weird-stock; tags: org_change, two_captions |
| `two-captions-weird-reddit-corporate` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | images: `image_1` weird, `image_2` meme-chaos; tags: multi_caption, reddit, two_captions |

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
| `wins-of-the-quarter-corporate` | The quarter's wins, celebrated: three photos, each captioned with a win, the last one the punchline (a win that isn't one) | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Wins of the quarter'; `caption_1`: a win, in two to four words; `caption_2`: another win, in two to four words; `caption_3`: the last win, the punchline, in two to four words; images: `image_1` corporate-stock, else photo, `image_2` corporate-stock, else photo, `image_3` corporate-stock, else photo; tags: three_captions, wins |

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
| `actual-vs-target-corporate` | The quarter's results against their target: the target as one line that climbs, and the actual results as a second line, which appears on a click, as the punchline | the default; `title`: the chart's claim, as a business review puts it; `shape`: how the target goes: rising, exponential or hockey stick; `line`: the target's name in the legend, such as 'Target'; `second_line`: the actual results' name in the legend, such as 'Actual'; `second_shape`: how the actual results go: flat, falling, dip, rollercoaster, crash or peak; `event`: a moment on the target's line, where it takes off, such as a board meeting; tags: chart, kpis, trend_chart |

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
| `results-by-region-corporate` | The results by region or team, as a ranking in bars: the company's regions and teams, and the last bar, the punchline, which wins by far | the default; `title`: what the ranking compares, as a business review's chart has it; `bars`: three to five regions or teams (only their names), separated by \|, and last an unlikely team that wins by far; `value_axis`: the measure, such as '% of target'; tags: bar_chart, chart, kpis |

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
| `synergies-corporate` | The synergies, as a Venn diagram: two or three parts of the company (or things it does, or a company it bought) that seem to have nothing in common, and the synergy where they overlap, the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Synergies'; `overlap`: the synergy, the punchline; tags: synergies, venn_diagram |

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
| `priority-matrix-corporate` | The strategic priorities, as a 2×2 matrix: the company's initiatives in three of its quadrants, and its initiative about the topic as the dot, alone in the best one | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Strategic priorities'; `x_left`: the bad end of the axis along the bottom; `x_right`: its good end, the opposite of the bad one; `y_bottom`: the bad end of the axis going up; `y_top`: its good end, the opposite of the bad one; `top_left`: an initiative of the company, by its made-up name alone; `bottom_left`: an initiative of the company, by its made-up name alone; `bottom_right`: an initiative of the company, by its made-up name alone; `top_right`: the label of the quadrant that's best on both axes, such as 'Quick wins'; `dot`: the initiative about the topic, by its made-up name; `dot_quadrant`: top right, the quadrant that's best on both axes; tags: matrix_diagram, synergies |

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
| `headline-number-corporate` | The quarter in one number: a share of its target just short of it, or a growth that's suspiciously small, presented as a triumph | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'The quarter in one number'; `number`: the number as people read it, with its unit, such as '97%' or '+0.3%'; `label`: what the number measures, without the number itself; `source`: a made-up, unreliable source, such as a preliminary report; images: `background` backdrop; tags: big_number, kpis |
| `the-ask-in-numbers-corporate` | The ask, as one big number: how much more leadership needs from everyone, and of what | `title`: the slide's title, as an all-hands deck's slide has it, such as 'Our ask'; `number`: the number as people read it, with its unit, such as '110%'; `label`: what it is of, and from whom, without the number itself; `source`: the small print, such as when it starts; images: `background` backdrop; tags: ask |

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
| `kpi-dashboard-corporate` | The KPIs against their targets, as figures on tiles: each a number and what it measures, the first a share of its target, the last one the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'KPIs against target'; `number_1`: the number as people read it, with its unit, such as '97%' or '+0.3%'; `number_2`: the number as people read it, with its unit, such as '97%' or '+0.3%'; `number_3`: the number as people read it, with its unit, such as '97%' or '+0.3%'; `number_4`: the number as people read it, with its unit, such as '97%' or '+0.3%'; `label_1`: what the number measures, without the number itself; `label_2`: what the number measures, without the number itself; `label_3`: what the number measures, without the number itself; `label_4`: what the number measures, without the number itself; images: `background` backdrop; tags: kpi, kpis |

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
| `ceo-s-post-corporate` | The CEO's post about the quarter, as leaders post on a business network: a lesson drawn from something trivial, or pride in the wrong thing | the default; `title`: a title such as 'From our CEO', or empty for none; `author`: the CEO's made-up name (never a real person); images: `photo` corporate-stock, else photo; tags: social_post, wins |

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
| `news-headline-corporate` | A made-up news story about the concept, as breaking news | the default; images: `photo` neutral (or generated, from its prompt, with an image generator set up); tags: news |

## `agenda`

The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the agenda's title |
| `items` | 200 | three to five items, separated by \|, each at most 45 characters |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `agenda-corporate` | The all-hands' agenda: the parts it goes through, in order, from a welcome to Q&A | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Agenda'; `items`: three to five parts of the all-hands, in the order they come, separated by \|, each at most 45 characters; tags: agenda, agenda |

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
| `q-a-corporate` | The closing slide, inviting everyone's questions, as at an all-hands | the default; `subtitle`: a line under it, such as where the questions go instead; images: `photo` weird-stock (or generated, from its prompt, with an image generator set up); tags: qa, questions |

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
| `roadmap-corporate` | The roadmap: what the company will do when, soonest first, the last moment the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Roadmap'; `date_1`: a quarter or a year, such as 'Q3' or 'FY27'; `date_2`: a quarter or a year, such as 'Q3' or 'FY27'; `date_3`: a quarter or a year, such as 'Q3' or 'FY27'; `date_4`: a quarter or a year, such as 'Q3' or 'FY27'; `date_5`: a quarter or a year, such as 'Q3' or 'FY27'; `event_1`: what the company does then, in two to four words; `event_2`: what the company does then, in two to four words; `event_3`: what the company does then, in two to four words; `event_4`: what the company does then, in two to four words; `event_5`: what the company does then, in two to four words; tags: roadmap, timeline |

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
| `new-hierarchy-corporate` | The new hierarchy, as a pyramid: everyone at its base, the levels above them, and who's at the top, the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'The new hierarchy'; tags: org_change, pyramid |

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
| `sales-pipeline-corporate` | The sales pipeline, as a funnel: the many leads at its top, each stage a number and what they did, down to the deals at the bottom, the punchline (one deal, say, and with whom) | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Our pipeline'; `stage_1`: the leads at the top: a number and who they are; `stage_2`: a number and what they did; `stage_3`: a number and what they did; `stage_4`: a number and what they did; `stage_5`: the deals at the bottom: a number and who with, the punchline; tags: funnel, kpis |

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
| `planning-cycle-corporate` | The planning cycle: three to five steps of how the company plans, each leading to the next, and the last back to the first | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Our planning cycle'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: cycle, roadmap |

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
| `new-structure-corporate` | The org change, as the new org chart: the teams and roles, under who's in charge now, the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Our new structure'; `boss`: who's in charge now, in a few words: the punchline; `report_1`: a team or a role, in a few words (without a person's name); `report_2`: a team or a role, in a few words (without a person's name); `report_3`: a team or a role, in a few words (without a person's name); `report_4`: a team or a role, in a few words (without a person's name); tags: org_change, org_chart |

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
| `new-process-corporate` | How the company works from now on, as a process, step by step, the last one the punchline (a step that undoes the others, say) | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Our new process'; `step_1`: a step, in two to four words; `step_2`: a step, in two to four words; `step_3`: a step, in two to four words; `step_4`: a step, in two to four words; `step_5`: a step, in two to four words; tags: process, roadmap |

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
| `meme-corporate` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-corporate` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

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
| `acronym-corporate` | A made-up method for the concept, as an acronym sold as the key to it all: its words get less plausible letter by letter, and the last one is the punchline | the default; tags: acronym |

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
| `tier-list-corporate` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

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
| `executive-summary-corporate` | The quarter's executive summary, as a wall of text that nobody can read: dense points of corporate jargon about the company's business, and one absurd point hidden among them, the punchline | the default; `title`: the slide's title, as an all-hands deck's slide has it, such as 'Executive summary'; tags: agenda, wall_of_text |

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
| `alignment-chart-corporate` | An alignment chart of things to do with the concept, as Dungeons & Dragons sorts characters: harmless and wholesome as lawful good, unhinged as chaotic evil, the punchline | the default; tags: alignment_chart |

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
| `customer-reviews-corporate` | What customers said this quarter, as reviews with stars: glowing ones, and the last one, the punchline, a one-star review | the default; `title`: a title such as 'Voice of the customer', or empty for none; tags: reviews, wins |

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
| `error-message-corporate` | A fake error message about the concept, as if the talk itself just crashed: a dialog with a playful, absurd message about the concept, worded as computers word them, and buttons, the last one the punchline | the default; tags: error_message |
