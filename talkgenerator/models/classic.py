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

# slide type -> {Slide argument: element role}, in the order the elements appear on the slide
CLASSIC_ROLES: Final[dict[str, dict[str, str]]] = {
    "title": {"title": "title", "subtitle": "subtitle"},
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
    "chart": {"title": "title", "chart_data": "chart"},
    # (New in v5: a Venn diagram or a 2×2 matrix, drawn as shapes where the 2019 template has its content)
    "diagram": {"title": "title", "diagram": "diagram"},
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
    "section": {"kicker": "kicker", "title": "title", "subtitle": "subtitle"},
    "questions": {"title": "title", "subtitle": "subtitle", "mark": "mark"},
    # (native diagrams, drawn as texts on shapes too)
    "timeline": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 6) for part in ("date", "event")},
    },
    "pyramid": {"title": "title", **{f"level_{number}": f"level_{number}" for number in range(1, 5)}},
    "funnel": {"title": "title", **{f"stage_{number}": f"stage_{number}" for number in range(1, 6)}},
    "cycle": {"title": "title", **{f"step_{number}": f"step_{number}" for number in range(1, 6)}},
    "org_chart": {
        "title": "title",
        "boss": "boss",
        **{f"report_{number}": f"report_{number}" for number in range(1, 5)},
    },
    "iceberg": {"title": "title", "tip": "tip", **{f"hidden_{number}": f"hidden_{number}" for number in range(1, 4)}},
    # (the talk formats': a method, or how a product works)
    "process": {"title": "title", **{f"step_{number}": f"step_{number}" for number in range(1, 6)}},
    # (a meme: a template's picture, with its captions as texts on it, where the template has them)
    "meme": {"template": "template", **{f"text_{number}": f"text_{number}" for number in range(1, 5)}},
    # (slide types from PowerPoint karaoke decks: docs/v5-plan.md, section 8)
    "fun_fact": {"photo": "photo", "kicker": "kicker", "fact": "fact", "source": "source"},
    "acronym": {
        "title": "title",
        **{f"{part}_{number}": f"{part}_{number}" for number in range(1, 7) for part in ("letter", "word")},
    },
    "dare": {"kicker": "kicker", "dare": "dare"},
    "flowchart": {
        "title": "title",
        **{role: role for role in ("question", "yes", "no", "yes_step", "no_step", "end")},
    },
    "tier_list": {
        "title": "title",
        **{
            role: role
            for tier in "sabcf"
            for role in (f"tier_{tier}", *(f"item_{tier}_{number}" for number in range(1, 4)))
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
    },
    "red_flags": {"title": "title", **{f"flag_{number}": f"flag_{number}" for number in range(1, 6)}},
    "reviews": {
        "title": "title",
        **{
            f"{part}_{number}": f"{part}_{number}" for number in range(1, 4) for part in ("stars", "review", "reviewer")
        },
    },
    "error_message": {
        "title": "window_title",  # (the dialog's, in its title bar: no title of the slide's)
        "icon": "icon",
        "message": "message",
        "code": "code",
        **{f"button_{number}": f"button_{number}" for number in range(1, 4)},
    },
}

# The slide types that came from real PowerPoint karaoke decks (docs/v5-plan.md, section 8)
KARAOKE_TYPES: Final = frozenset(
    {"fun_fact", "acronym", "dare", "flowchart", "tier_list"}
    | {"wall_of_text", "alignment_chart", "red_flags", "reviews", "error_message"}
)
# The slide types that the talk formats beyond TED-like talks brought (docs/v5-plan.md, section 7)
FORMAT_TYPES: Final = frozenset({"process"})

# The slide types that the 2019 template has no layout for (all of milestone 6's): a classic deck draws them as a
# themed deck does, laid out in the template's look (talkgenerator.design.themes.CLASSIC_LOOK), on its blank slide
DRAWN_TYPES: Final = frozenset(
    {"big_number", "kpi", "quiz", "social_post", "news_headline", "agenda", "section", "questions"}
    | {"timeline", "pyramid", "funnel", "cycle", "org_chart", "iceberg", "meme"}
    | KARAOKE_TYPES
    | FORMAT_TYPES
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
    "timeline": ("date_1", "event_1", "date_2", "event_2", "date_3", "event_3"),
    "pyramid": ("level_1", "level_2", "level_3"),
    "funnel": ("stage_1", "stage_2", "stage_3"),
    "cycle": ("step_1", "step_2", "step_3"),
    "org_chart": ("boss", "report_1", "report_2"),
    "iceberg": ("tip", "hidden_1", "hidden_2"),
    "process": ("step_1", "step_2", "step_3"),
    "meme": ("template", "text_1"),
    "fun_fact": ("kicker", "fact"),
    "acronym": ("letter_1", "word_1", "letter_2", "word_2", "letter_3", "word_3"),
    "dare": ("kicker", "dare"),
    "flowchart": ("question", "yes_step", "no_step", "end"),
    "tier_list": ("tier_s", "item_s_1", "tier_a", "item_a_1"),
    "wall_of_text": ("title", *(f"point_{number}" for number in range(1, 6)), "highlight"),
    "alignment_chart": ALIGNMENTS,
    "red_flags": ("flag_1", "flag_2", "flag_3"),
    "reviews": ("stars_1", "review_1", "stars_2", "review_2"),  # (a review's stars read as "4/5" beside them)
    "error_message": ("message", "button_1", "button_2"),
}

# The roles of drawn slides that hold pictures: a post's or a story's photo, a meme's template, the picture behind a
# big number or KPI tiles
IMAGE_ROLES: Final = frozenset({"photo", "template", "background"})

# Roles that only ever hold text, even when the text looks like an image's file name
TEXT_ROLES: Final = frozenset(
    {"title", "subtitle", "text", "caption_1", "caption_2", "caption_3"}
    | {role for slide_type in DRAWN_TYPES for role in CLASSIC_ROLES[slide_type].values() if role not in IMAGE_ROLES}
)

# Images that fill their frame (cropped where needed) instead of being shown whole
COVER_ROLES: Final = frozenset({"background", "photo"})


def layout_id(slide_type: str) -> str:
    return "classic/" + slide_type


def highlighted_at(points: int) -> int:
    """Where a wall of text hides its highlighted point among its others: after this many of them (a little past the
    middle, where nobody would look for it)."""
    return round(points * 0.6)
