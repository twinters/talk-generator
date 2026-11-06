"""The classic layouts: how the slide types of the 2019 generator name their content in a deck.

For every classic slide type: which argument of its `Slide` class (see `talkgenerator.slide.slides`) becomes which
element role. The PowerPoint renderer reads the same table the other way around, to fill the classic template.
"""

from __future__ import annotations

from typing import Final

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
}

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
}

# Roles that only ever hold text, even when the text looks like an image's file name
TEXT_ROLES: Final = frozenset({"title", "subtitle", "text", "caption_1", "caption_2", "caption_3"})

# Images that fill their frame (cropped where needed) instead of being shown whole
COVER_ROLES: Final = frozenset({"background"})


def layout_id(slide_type: str) -> str:
    return "classic/" + slide_type
