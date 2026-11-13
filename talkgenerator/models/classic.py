"""The classic layouts: how the slide types of the 2019 generator name their content in a deck.

For every classic slide type: which argument of its `Slide` class (see `talkgenerator.slide.slides`) becomes which
element role. The PowerPoint renderer reads the same table the other way around, to fill the classic template.
"""

from __future__ import annotations

from typing import Final

# A wall of text's bullets: a point's, and a point's under the one before it
TOP_BULLET: Final = "• "
SUB_BULLET: Final = "– "

# An alignment chart's cells, in reading order: lawful to chaotic across, good to evil down (as Dungeons & Dragons
# has them)
ALIGNMENTS: Final = (
    *("lawful_good", "neutral_good", "chaotic_good"),
    *("lawful_neutral", "true_neutral", "chaotic_neutral"),
    *("lawful_evil", "neutral_evil", "chaotic_evil"),
)


# A picture equation's things, in order: the first, the second, and what the two make together, the punchline (D78)
EQUATION: Final = ("term_1", "term_2", "result")


def _pictures(*boxes: str) -> dict[str, str]:
    """The roles of the pictures of a diagram's boxes (docs/v5-plan.md, D64), by the roles of the boxes' texts."""
    return {f"{box}_picture": f"{box}_picture" for box in boxes}


def _boxes(prefix: str, most: int) -> dict[str, str]:
    """A diagram's numbered boxes (prefix_1, prefix_2...), each its text and its picture's role."""
    return {
        role: role for number in range(1, most + 1) for role in (f"{prefix}_{number}", f"{prefix}_{number}_picture")
    }


# slide type -> {Slide argument: element role}, in the order the elements appear on the slide
CLASSIC_ROLES: Final[dict[str, dict[str, str]]] = {
    "title": {"title": "title", "subtitle": "subtitle", "picture": "title_picture"},
    "large_quote": {"title": "title", "text": "text", "background_image": "background"},
    "image": {"title": "title", "image_url": "content"},
    "full_image": {"title": "title", "image_url": "content"},
    "two_column_image": {
        "title": "title",
        "caption_1": "caption_1",
        "image_or_text_1": "content_1",
        "caption_2": "caption_2",
        "image_or_text_2": "content_2",
    },
    "three_column_image": {
        "title": "title",
        "caption_1": "caption_1",
        "image_or_text_1": "content_1",
        "caption_2": "caption_2",
        "image_or_text_2": "content_2",
        "caption_3": "caption_3",
        "image_or_text_3": "content_3",
    },
    # (and a picture by a trend's named point, on a click: docs/v5-plan.md, D64)
    "chart": {"title": "title", "chart_data": "chart", "point_picture": "point_picture"},
    # (New in v5: a Venn diagram or a 2×2 matrix, drawn as shapes where the 2019 template has its content, with
    # pictures by its first two circles or in some of its quadrants, now and then)
    "diagram": {
        "title": "title",
        "diagram": "diagram",
        **_pictures("circle_1", "circle_2", "top_left", "top_right", "bottom_left", "bottom_right"),
    },
    # (New in v5 too, and drawn as shapes in the template's colours, on its blank slide: see DRAWN_TYPES)
    # (a big number's and KPI tiles' picture, if any, behind them or beside them: D63)
    "big_number": {
        "background": "background",
        "title": "title",
        "number": "number",
        "label": "label",
        "source": "source",
    },
    "kpi": {
        "background": "background",
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 5) for part in ("number", "label")},
    },
    "quiz": {
        "question": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 5) for part in ("letter", "option")},
        "answer": "answer",
        "explanation": "explanation",
    },
    "social_post": {
        "title": "title",
        "initials": "initials",
        "author": "author",
        "handle": "handle",
        "text": "text",
        "photo": "photo",
        "stats": "stats",
    },
    "news_headline": {
        "photo": "photo",
        "kicker": "kicker",
        "outlet": "outlet",
        "headline": "headline",
        "subheadline": "subheadline",
    },
    "agenda": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 6) for part in ("number", "item")},
    },
    # (a section and a dare over a picture of what they're about, if they have one: D80)
    "section": {"background": "background", "kicker": "kicker", "title": "title", "subtitle": "subtitle"},
    # (the closing slide, with a picture to end on, if it has one: docs/v5-plan.md, D65)
    "questions": {"photo": "photo", "title": "title", "subtitle": "subtitle", "mark": "mark"},
    # (the talk's closer, after its last slide: its big words, a line under them, a small note, and a huge question
    # mark beside them for a question: D76)
    "closer": {"title": "title", "subtitle": "subtitle", "note": "note", "mark": "mark"},
    # (native diagrams, drawn as texts on shapes too)
    "timeline": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 6) for part in ("date", "event")},
    },
    # (each box's picture, if it has one, after its text: docs/v5-plan.md, D64)
    "pyramid": {"title": "title", **_boxes("level", 4)},
    "funnel": {"title": "title", **_boxes("stage", 5)},
    "cycle": {"title": "title", **_boxes("step", 5)},
    "org_chart": {
        "title": "title",
        "boss": "boss",
        **_pictures("boss"),  # (who's in charge, as a picture in their name's place: a pattern break, D73)
        **{f"report_{number}": f"report_{number}" for number in range(1, 5)},
    },
    "iceberg": {"title": "title", "tip": "tip", **_pictures("tip"), **_boxes("hidden", 3)},
    # (the talk formats': a method, or how a product works; an academic talk's references, with a picture of one)
    "process": {"title": "title", **_boxes("step", 5)},
    "references": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 6) for part in ("number", "item")},
        "figure": "figure",
        "caption": "caption",
    },
    # (the talk's why, early on, over a picture of it or beside one: D69)
    "problem": {
        "background": "background",
        "photo": "photo",
        "kicker": "kicker",
        "problem": "problem",
        "detail": "detail",
    },
    # (a meme: a template's picture, with its captions as texts on it, where the template has them)
    "meme": {"template": "template", **{f"text_{number}": f"text_{number}" for number in range(1, 5)}},
    # (slide types from PowerPoint karaoke decks: docs/v5-plan.md, section 8)
    "fun_fact": {"photo": "photo", "kicker": "kicker", "fact": "fact", "source": "source"},
    "acronym": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 7) for part in ("letter", "word")},
    },
    "dare": {"background": "background", "kicker": "kicker", "dare": "dare"},
    "flowchart": {
        "title": "title",
        **{role: role for role in ("question", "yes", "no", "yes_step", "no_step", "end")},
        **_pictures("yes_step", "no_step", "end"),
    },
    "tier_list": {
        "title": "title",
        **{
            role: role
            for tier in "sabcf"
            for role in (f"tier_{tier}", *(f"item_{tier}_{number}" for number in range(1, 4)), f"item_{tier}_1_picture")
        },
    },
    # (and the next ones from the karaoke catalogue: a wall of text, an alignment chart, red flags, reviews with
    # stars and a fake error message)
    "wall_of_text": {
        "title": "title",
        **{f"point_{number}": f"point_{number}" for number in range(1, 17)},
        "highlight": "highlight",
        "continued": "continued",
    },
    "alignment_chart": {
        "title": "title",
        **{f"column_{number}": f"column_{number}" for number in range(1, 4)},
        **{f"row_{number}": f"row_{number}" for number in range(1, 4)},
        **{alignment: alignment for alignment in ALIGNMENTS},
        **_pictures(*ALIGNMENTS),
    },
    "red_flags": {"title": "title", **_boxes("flag", 5)},
    "traffic_flags": {"title": "title", **_boxes("flag", 3)},  # (a green, an orange and a red flag)
    "reviews": {
        "title": "title",
        **{
            role: role
            for number in range(1, 4)
            for role in (f"stars_{number}", f"review_{number}", f"review_{number}_picture", f"reviewer_{number}")
        },
    },
    "error_message": {
        "title": "window_title",  # (the dialog's, in its title bar: no title of the slide's)
        "icon": "icon",
        "message": "message",
        "code": "code",
        **{f"button_{number}": f"button_{number}" for number in range(1, 4)},
    },
    # (slides of a surprising picture the presenter has to explain, with little or no text: D78. An exhibit's label is
    # its word and its letter, "Exhibit A", where an evidence marker shows its letter alone; an equation's things are
    # pictures, or else emoji, with a "+" and a "=" between them; without a picture, "What do you see?" is an inkblot,
    # which its layout draws)
    "exhibit": {"picture": "picture", "letter": "letter", "label": "label", "case": "case", "note": "note"},
    "pick_one": {"picture_1": "picture_1", "picture_2": "picture_2", "title": "title", "or": "or"},
    "equation": {
        "title": "title",
        **{role: role for thing in EQUATION for role in (thing, f"{thing}_picture")},
        "plus": "plus",
        "equals": "equals",
    },
    "what_do_you_see": {"picture": "picture", "question": "question"},
    "before_after": {
        "title": "title",
        **{role: role for when in ("before", "after") for role in (f"{when}_picture", when)},
    },
}

# The slide types that came from real PowerPoint karaoke decks (docs/v5-plan.md, section 8)
KARAOKE_TYPES: Final = frozenset(
    {"fun_fact", "acronym", "dare", "flowchart", "tier_list"}
    | {"wall_of_text", "alignment_chart", "red_flags", "reviews", "error_message"}
    | {"traffic_flags"}
)
# The slide types that the talk formats beyond TED-like talks brought (docs/v5-plan.md, section 7)
FORMAT_TYPES: Final = frozenset({"process", "references"})
# The problem slide, a talk's why: what pitches and academic talks open on, and some TED-like talks too (D69)
PROBLEM_TYPES: Final = frozenset({"problem"})
# The talk's closer, the slide after its last (D76)
CLOSER_TYPES: Final = frozenset({"closer"})
# The slides of a surprising picture that the presenter has to explain, with little or no text, as improv suggestions
# and story cubes give a performer something to explain (D78)
PICTURE_PROMPT_TYPES: Final = frozenset({"exhibit", "pick_one", "equation", "what_do_you_see", "before_after"})

# The slide types that the 2019 template has no layout for (all of milestone 6's): a classic deck draws them as a
# themed deck does, laid out in the template's look (talkgenerator.design.themes.CLASSIC_LOOK), on its blank slide
DRAWN_TYPES: Final = frozenset(
    {"big_number", "kpi", "quiz", "social_post", "news_headline", "agenda", "section", "questions"}
    | {"timeline", "pyramid", "funnel", "cycle", "org_chart", "iceberg", "meme"}
    | KARAOKE_TYPES
    | FORMAT_TYPES
    | PROBLEM_TYPES
    | CLOSER_TYPES
    | PICTURE_PROMPT_TYPES
)

# The roles a slide of each type can't do without: its Slide class's required_arguments, as roles
REQUIRED_ROLES: Final[dict[str, tuple[str, ...]]] = {
    "title": ("title",),
    "large_quote": ("text", "background"),
    "image": ("content",),
    "full_image": ("content",),
    "two_column_image": ("content_1", "content_2"),
    "three_column_image": ("content_1", "content_2", "content_3"),
    "chart": ("chart",),
    "diagram": ("diagram",),
    "big_number": ("number", "label"),
    "kpi": ("number_1", "label_1", "number_2", "label_2", "number_3", "label_3"),
    "quiz": ("title", "option_1", "option_2", "option_3", "answer"),
    "social_post": ("author", "text"),
    "news_headline": ("outlet", "headline", "photo"),
    "agenda": ("item_1", "item_2", "item_3"),
    "section": ("title",),
    "questions": ("title",),
    "closer": ("title",),
    "timeline": ("date_1", "event_1", "date_2", "event_2", "date_3", "event_3"),
    "pyramid": ("level_1", "level_2", "level_3"),
    "funnel": ("stage_1", "stage_2", "stage_3"),
    "cycle": ("step_1", "step_2", "step_3"),
    "org_chart": ("boss", "report_1", "report_2"),
    "iceberg": ("tip", "hidden_1", "hidden_2"),
    "process": ("step_1", "step_2", "step_3"),
    "references": ("item_1", "item_2", "item_3"),
    "problem": ("kicker", "problem"),
    "meme": ("template", "text_1"),
    "fun_fact": ("kicker", "fact"),
    "acronym": ("letter_1", "word_1", "letter_2", "word_2", "letter_3", "word_3"),
    "dare": ("kicker", "dare"),
    "flowchart": ("question", "yes_step", "no_step", "end"),
    "tier_list": ("tier_s", "item_s_1", "tier_a", "item_a_1"),
    "wall_of_text": ("title", *(f"point_{number}" for number in range(1, 6)), "highlight"),
    "alignment_chart": ALIGNMENTS,
    "red_flags": ("flag_1", "flag_2", "flag_3"),
    "traffic_flags": ("flag_1", "flag_2", "flag_3"),
    "reviews": ("stars_1", "review_1", "stars_2", "review_2"),  # (a review's stars read as "4/5" beside them)
    "error_message": ("message", "button_1", "button_2"),
    # (an equation's thing is its picture or else its emoji: a required role is there with either, D78)
    "exhibit": ("label", "picture"),
    "pick_one": ("title", "picture_1", "picture_2"),
    "equation": EQUATION,
    "what_do_you_see": ("question",),
    "before_after": ("before", "before_picture", "after", "after_picture"),
}

# The roles of the pictures in diagrams' boxes (docs/v5-plan.md, D64), and by a trend's named point (and an equation's
# things', a before's and an after's, D78)
PICTURE_ROLES: Final = frozenset(
    role for roles in CLASSIC_ROLES.values() for role in roles.values() if role.endswith("_picture")
)
# The pictures to pick from, and the picture to explain, as evidence or to see something in (D78)
PROMPT_PICTURES: Final = frozenset({"picture", "picture_1", "picture_2"})
# The roles of drawn slides that hold pictures: a post's or a story's photo, a meme's template, a work's figure (D65),
# the picture behind a big number or KPI tiles (D63), a box's picture, and the pictures to explain (D78)
IMAGE_ROLES: Final = frozenset({"photo", "template", "figure", "background"}) | PICTURE_ROLES | PROMPT_PICTURES

# Roles that only ever hold text, even when the text looks like an image's file name
TEXT_ROLES: Final = frozenset(
    {"title", "subtitle", "text", "caption_1", "caption_2", "caption_3"}
    | {role for slide_type in DRAWN_TYPES for role in CLASSIC_ROLES[slide_type].values() if role not in IMAGE_ROLES}
)

# Images that fill their frame (cropped where needed) instead of being shown whole (two pictures to pick from too, in
# boxes of one size; the picture to explain shows whole, in a box its layout makes as tall as it is: D78)
COVER_ROLES: Final = frozenset({"background", "photo", "picture_1", "picture_2", "title_picture"}) | PICTURE_ROLES


def layout_id(slide_type: str) -> str:
    return "classic/" + slide_type


def highlighted_at(points: int) -> int:
    """Where a wall of text hides its highlighted point among its others: after this many of them (a little past the
    middle, where nobody would look for it)."""
    return round(points * 0.6)
