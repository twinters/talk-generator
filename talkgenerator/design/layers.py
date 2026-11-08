"""What's behind a place on a slide, as its elements are drawn one over the other: the colours a text there has to
read on. The layout engine picks colours with it (the credits'), and the design checks check them with it
(talkgenerator.checks.design)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from talkgenerator.design import color, geometry
from talkgenerator.models.deck import Box, Content, ImageElement, ShapeElement, SlideBackground

# How tall a line's letters are, from the top of its capitals to the bottom of its descenders, as a share of its size
GLYPHS: Final = 0.8
# What a picture could be behind a text: anything, so the worst of black and white (for a text that has to read at
# 4.5 or 3, a grey between them is no worse)
ANYTHING: Final = ("#000000", "#ffffff")


def letters(lines: Sequence[Box], size: float) -> list[Box]:
    """Where a text's letters are, line by line (each line's box, as tall as its letters, in its middle): what has to
    be behind them for the text to read (a cursor after its last word, or the edge of a tile around it, isn't)."""
    height = GLYPHS * size
    return [Box(x=line.x, y=line.y + (line.h - height) / 2, w=line.w, h=height) for line in lines]


def behind_letters(
    background: SlideBackground | None,
    elements: Sequence[Content],
    lines: Sequence[Box],
    size: float,
    anything: Sequence[str] = ANYTHING,
) -> list[str]:
    """The colours that may be behind a text's letters (see behind)."""
    colours: list[str] = []
    for area in letters(lines, size):
        colours += [colour for colour in behind(background, elements, area, anything) if colour not in colours]
    return colours


def behind(
    background: SlideBackground | None, elements: Sequence[Content], box: Box, anything: Sequence[str] = ANYTHING
) -> list[str]:
    """The colours that may be behind a box: the slide's background (both ends of a gradient, and where its pattern's
    lines or dots are), as the elements drawn before it (in order) change it. A picture under the box's middle could
    be anything (the worst of black and white, or of the colours given: a text that reads at a lower contrast, such
    as the credit line, could read on both and not on a grey). A shape over all of the box puts its colour behind all
    of it; one over a part of it (or its outline crossing it), its colour behind that part: so the box may have
    either."""
    backgrounds = [background.color] if background is not None else ["#ffffff"]
    if background is not None and background.color_2:
        backgrounds.append(background.color_2)
    if background is not None and background.pattern is not None:
        pattern = background.pattern
        backgrounds += [color.mix(colour, pattern.color, pattern.opacity) for colour in backgrounds]
    center_x, center_y = box.x + box.w / 2, box.y + box.h / 2
    for element in elements:
        area = element.box
        if area is None:
            continue
        if isinstance(element, ImageElement):
            if area.x <= center_x <= area.x + area.w and area.y <= center_y <= area.y + area.h:
                backgrounds = list(anything)  # an image could be anything
        elif isinstance(element, ShapeElement) and geometry.touches(element, box):
            mixed: list[str] = []
            if element.filled:
                mixed = [color.mix(colour, element.color, element.opacity) for colour in backgrounds]
            if element.outline and element.outline_width > 0 and not geometry.covers(inside_outline(element), box):
                mixed += [color.mix(colour, element.outline, element.opacity) for colour in backgrounds]
            whole = element.filled and geometry.covers(element, box)  # (none of what was behind it shows)
            backgrounds = list(dict.fromkeys(mixed if whole else [*backgrounds, *mixed]))
    return backgrounds


def drawn_over(shape: ShapeElement, box: Box) -> bool:
    """Whether the shape is drawn anywhere over the box: its fill, or (without one) its outline."""
    if not geometry.touches(shape, box):
        return False
    return shape.filled or not geometry.covers(inside_outline(shape), box)


def inside_outline(shape: ShapeElement) -> ShapeElement:
    """What's inside the shape's outline: the shape, smaller by the outline's width on every side."""
    width = shape.outline_width if shape.outline else 0.0
    box = shape.box
    inner = Box(x=box.x + width, y=box.y + width, w=max(0.0, box.w - 2 * width), h=max(0.0, box.h - 2 * width))
    return shape.model_copy(update={"box": inner, "corner": max(0.0, shape.corner - width)})
