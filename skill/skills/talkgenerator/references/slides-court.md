# The slides of a `court` talk

A court case in which the topic stands trial for a harmless crime: the charges, the evidence, a witness, the alibi, an objection, the closing argument and the verdict, each a part of its arc, in that order.

Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` (or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the talk is over in its language and format ("Thank you!" and "Questions?", "Let's talk" for a pitch): a plan needs no slide for that. A slide's `recipe` picks its look and its image sources, and makes the slide the classic way when it can't be made as planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, gifs and memes, and so on (`talkgenerator formats --looks` lists them all).

Made by `talkgenerator formats --details --format court`.

A plan's `title` is like a court case's name or a true-crime story's: 'The People v.' and the topic, or the case of something petty that went missing, and its `presenter_job` is their part in the trial, as the court introduces them: the prosecutor, the counsel for the defence or the detective on the case.

## The arc

A talk of this format goes through these parts, in this order, each with the slides of its recipes: a talk too short for all of them keeps the most important ones, and a long one gives some of them more slides, with the format's other slides in between. A plan reads as one of this format when its slides follow the arc (talkgenerator doesn't hold a plan to it).

| Part | Slides | Recipes |
| --- | --- | --- |
| `charges` | 1 | `breaking-news-court`, `the-charges-court`, `the-people-versus-court` |
| `evidence` | 1 to 2 | `exhibit-a-court`, `forensic-analysis-court` |
| `witness` | 1 | `the-witnesses-court`, `where-was-the-defendant-court`, `witness-statement-court` |
| `alibi` | 1 | `alibi-check-court`, `alibi-not-found-court`, `the-night-in-question-court` |
| `objection` | 1 | `objection-court`, `objection-your-honour-court` |
| `closing_argument` | 1 | `closing-argument-court`, `look-at-this-face-court`, `signs-of-guilt-court` |
| `verdict` | 1 | `the-jury-decides-court`, `the-verdict-court`, `you-are-the-jury-court` |

## `image`

An image with a title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `single-image-copyright-free` | A photo with a title | the default; images: `image` photo; tags: single_image |

## `full_image`

An image filling the slide, with an optional title.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 60 | the slide's title (or empty, for none) |

Images: `image`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `objection-court` | An objection, shouted in court: a dramatic photo filling the slide, under 'Objection!' and an absurd reason | the default; `title`: 'Objection!' and its reason, in a few words; images: `image` weird-stock; tags: full_image, objection |
| `look-at-this-face-court` | The defendant, in a photo filling the slide, under a question to the jury: does this look like the face of someone who did it? | `title`: a question to the jury about the defendant's face, in a few words; images: `image` photo; tags: closing_argument, full_image |
| `full-screen-gif-court` | A gif, filling the slide | `title`: two to four words of your own that build up to the gif, or empty for none; images: `image` gifs; tags: full_image, gif |
| `full-screen-neutral-images-court` | A photo, filling the slide | images: `image` neutral; tags: full_image, neutral |
| `provocation-court` | A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the slide, under a provocative word or two | `title`: one or two provocative words, as a courtroom hears them, ending in a full stop or a question mark; images: `image` backdrop; tags: full_image, provocation |

## `statement`

A big text over a photo.

| Text | At most | What to write |
| --- | --- | --- |
| `text` | 140 | the big text over the photo |

Images: `background`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-people-versus-court` | The case opens: the court's solemn words over a photo, the People versus the topic, and what for | the default; `text`: the court's opening words, in one or two sentences, naming the case and the petty crime; images: `background` calm-backdrop or backdrop; tags: charges, statement |
| `objection-your-honour-court` | An objection, as one sentence over a photo: what counsel objects to, absurdly | `text`: the objection, in one sentence that starts with 'Objection'; images: `background` calm-backdrop or backdrop; tags: objection, statement |
| `closing-argument-court` | The closing argument, as one sentence to the jury over a photo: why it can only have been the topic | `text`: the closing argument, in one or two sentences to the jury; images: `background` calm-backdrop or backdrop; tags: closing_argument, statement |
| `full-screen-pixabay-deep-court` | A deep question over a photo | `text`: a short, deep question, such as 'But... why?'; images: `background` calm-backdrop or backdrop; tags: deep, full_image |

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
| `two-captions-gifs-court` | Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing | the default; images: `image_1` neutral or meme-chaos, `image_2` gifs, else weird; tags: gif, multi_caption, two_captions |

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
| `the-witnesses-court` | The witnesses: three photos, each captioned with who the witness is, the last one the punchline | the default; `title`: the slide's title, as a courtroom drama's slide has it, such as 'The witnesses'; `caption_1`: a witness, in two to four words; `caption_2`: another witness, in two to four words; `caption_3`: the last witness, the punchline, in two to four words; images: `image_1` photo, `image_2` photo, `image_3` photo; tags: three_captions, witness |

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
| `the-jury-decides-court` | The jury's verdict, as a pie chart: guilty or not, and a funny third answer | the default; `question`: the verdict's yes-or-no question: whether the defendant did it; tags: chart, verdict, yes_no_chart |

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
| `forensic-analysis-court` | The lab's forensic analysis, as a scatter plot of made-up data that proves the topic's guilt: the nearer the topic, the more of the evidence | the default; `title`: the lab's finding, as a claim in a few words; `x_axis`: how near the topic, or when, along the bottom; `y_axis`: how much of the evidence was found, such as crumbs; `outlier`: one point far from the others, named after another suspect; tags: chart, curve, evidence |

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
| `signs-of-guilt-court` | The case against the topic, as a Venn diagram: two or three signs of guilt (a motive, the chance, crumbs), and the defendant where they all meet, the punchline | the default; `title`: the slide's title, as a courtroom drama's slide has it, such as 'The case against' the topic; `overlap`: the defendant: the topic, in a few words; tags: closing_argument, venn_diagram |

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
| `the-verdict-court` | The verdict, as one big number: the jury's vote, or how long the harmless sentence lasts | the default; `title`: the slide's title, as a courtroom drama's slide has it, such as 'The verdict'; `number`: the number as people read it, with its unit: a vote, or a sentence's days or hours; `label`: what it counts, the vote or the harmless sentence, without the number itself; `source`: who decided it, such as the judge, after lunch; images: `background` backdrop; tags: big_number, verdict |

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
| `where-was-the-defendant-court` | A quiz for the audience, as if they were the detectives: where the defendant was on the night of the crime, with three or four places, the right one the most suspicious | the default; `question`: where the defendant was at the time of the crime, as a question to the audience; `explanation`: how the court knows, without naming another option; tags: quiz, witness |

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
| `witness-statement-court` | A witness's post about the night of the crime: what they saw or heard, as people post it, sure of the wrong details | the default; `title`: a title such as 'Witness statement', or empty for none; `author`: the witness's made-up name (never a real person); images: `photo` photo; tags: social_post, witness |

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
| `breaking-news-court` | The charges, as breaking news: a headline that the topic has been charged with a harmless, petty crime (never violence, weapons or anyone hurt), over a photo of the accused | the default; `outlet`: the made-up name of a newspaper or a channel that covers court cases; `headline`: the headline: what the topic is charged with, a harmless, petty crime (never violence, weapons or anyone hurt); `subheadline`: a line under it, with one more absurd detail of the case; images: `photo` photo; tags: charges, news |

## `agenda`

The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.

| Text | At most | What to write |
| --- | --- | --- |
| `title` | 40 | the agenda's title |
| `items` | 200 | three to five items, separated by \|, each at most 45 characters |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `the-charges-court` | The charges against the topic, read out as numbered counts: three to five harmless, petty crimes, the last one the punchline | the default; `title`: the slide's title, as a courtroom drama's slide has it, such as 'The charges'; `items`: three to five charges, separated by \|, each at most 45 characters, the last one the punchline; tags: agenda, charges |

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
| `the-night-in-question-court` | The night in question, as a timeline: what the defendant did, minute by minute, the last moment the punchline | the default; `title`: the slide's title, as a courtroom drama's slide has it, such as 'The night in question'; `date_1`: a time of that night, such as '21:13'; `date_2`: a time of that night, such as '21:13'; `date_3`: a time of that night, such as '21:13'; `date_4`: a time of that night, such as '21:13'; `date_5`: a time of that night, such as '21:13'; `event_1`: what the defendant did then, in two to four words; `event_2`: what the defendant did then, in two to four words; `event_3`: what the defendant did then, in two to four words; `event_4`: what the defendant did then, in two to four words; `event_5`: what the defendant did then, in two to four words; tags: alibi, timeline |

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
| `meme-court` | A meme about the concept | the default; images: `template` meme-templates; tags: caption_meme, meme |

## `fun_fact`

A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator adds it), with a made-up source, and a photo if it has one.

| Text | At most | What to write |
| --- | --- | --- |
| `fact` | 150 | the fact: one sentence, stated as certain, that the presenter has to back up |
| `source` | 60 | a made-up, unreliable source for the fact (or empty, for none) |

Images: `photo`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `fun-fact-court` | A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up | the default; images: `photo` neutral or meme-chaos; tags: fun_fact |

## `dare`

A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), which the audience then watches them keep up, or something the presenter has the whole audience do (talkgenerator adds its heading).

| Text | At most | What to write |
| --- | --- | --- |
| `dare` | 130 | the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking only in questions; hard to keep up, harmless, and for the presenter alone (or empty, for none) |
| `audience` | 130 | what the presenter has the whole audience do, said to them: a show of hands, a call and response (when the presenter says a word, everyone answers with another), the front row standing up, a sound everyone makes; harmless, fun to join in, and singling nobody out (or empty, for none) |

Images: none

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `you-are-the-jury-court` | The audience as the jury: what everyone does to give their verdict on the defendant | the default; `audience`: what the whole audience does to give its verdict, said to them: a show of hands, or a word said together; harmless, fun to join in, and singling nobody out; shows no `dare`; tags: dare, verdict |

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
| `alibi-check-court` | Checking the defendant's alibi, as a flowchart whose every answer leads to the same end: guilt | the default; `title`: a title such as 'The alibi', or empty for none; `question`: a yes-or-no question about the defendant's alibi; `end`: where both answers lead: the defendant's guilt, the punchline; tags: alibi, flowchart |

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
| `tier-list-court` | A tier list that ranks things to do with the concept as if it were science: arguable placements, and a surprising S tier as the punchline | the default; tags: tier_list |

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
| `alignment-chart-court` | An alignment chart of things to do with the concept, as Dungeons & Dragons sorts characters: harmless and wholesome as lawful good, unhinged as chaotic evil, the punchline | the default; tags: alignment_chart |

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
| `red-flags-court` | Red flags about the concept, as in dating advice: warning signs that someone or something around it is trouble, each more alarming than the last | the default; tags: red_flags |

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
| `alibi-not-found-court` | The defendant's alibi, as a fake error message from the court's records: it can't be found, with buttons, the last one the punchline | the default; `title`: the dialog's title, such as the court's records system; `buttons`: two or three buttons, separated by \|, each at most 20 characters: the last one the punchline, such as a confession; tags: alibi, error_message |

## `exhibit`

Exhibit A: one odd picture, as the evidence in a case, with an evidence tag beside it or a marker on it (talkgenerator adds 'Exhibit A' and a case number; a later exhibit in the talk is Exhibit B, of the same case), and a short note on the tag, if it has one: the presenter explains what it proves.

| Text | At most | What to write |
| --- | --- | --- |
| `note` | 40 | a few words on the evidence tag about the picture, as a police report notes where or when it was found (or empty, for none) |

Images: `picture`

| Recipe | What it's for | Notes |
| --- | --- | --- |
| `exhibit-a-court` | Exhibit A: an odd picture to do with the concept, as the evidence in a case, for the presenter to explain what it proves | the default; `picture_query`: an image search query for the odd picture that is the evidence: something concrete and surprising that the case could hinge on, in two to six plain English words; images: `picture` weird-stock (or generated, from its prompt, with an image generator set up); tags: evidence, exhibit |
