"""Diagrams drawn as PowerPoint shapes: Venn diagrams and 2×2 matrices.

A deck holds only a diagram's texts and where its dot goes (`VennDiagram`, `MatrixDiagram`), so a diagram needs no
image source and looks the same wherever the deck is drawn. In PowerPoint, it fills a frame: in the classic template,
where the title-and-content slide has its content, and in a themed deck, the box the layout engine gave it. It's
circles, rectangles and lines, with text boxes for the labels. python-pptx can't make shapes see-through, so the
circles' and quadrants' colours get their transparency in the fill's XML.

A classic diagram has the template's colours; a themed one has its theme's, in a `DiagramStyle` that the layout
engine picked (with colours that read on what's behind them), and its labels are measured in the theme's font. Where
a diagram's labels go, and at what size, is `labels()`, which the renderer, the previews and the design checks share.
A Venn diagram's labels go in its circles; when one doesn't fit there even at the smallest size (a long compound, as
Dutch and German have them), they all go beside the circles instead (see `venn_layout_for`).

A diagram whose `reveal` is "punchline" shows its punchline (a Venn diagram's overlap, a matrix's dot and its name) on
a click (see `talkgenerator.render.animation`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from talkgenerator.design import fit, fonts
from talkgenerator.models.deck import Box as CanvasBox
from talkgenerator.models.deck import DiagramStyle, MatrixDiagram, VennDiagram
from talkgenerator.render import animation
from talkgenerator.render.charts import PUNCHLINE_COLOUR

_INCH: Final = 914400  # EMU
EMU_PER_PIXEL: Final = 6350  # a pixel of the 1920×1080 canvas that themed decks are laid out on

# The 2019 template's colours (its theme's accents): blue, orange, green and purple
COLOURS: Final = (
    RGBColor(0x1B, 0x58, 0x7C),
    RGBColor(0xF0, 0x7F, 0x09),
    RGBColor(0x4E, 0x85, 0x42),
    RGBColor(0x60, 0x48, 0x78),
)
_AXIS_COLOUR: Final = RGBColor(0x40, 0x40, 0x40)
_WHITE: Final = RGBColor(0xFF, 0xFF, 0xFF)
CIRCLE_OPACITY: Final = 0.45  # so that where the circles overlap, their colours mix
QUADRANT_OPACITY: Final = 0.2

# Where the circles' centres are, as a share of their radius: two circles, either side of the diagram's middle; three,
# on a triangle around it (two on top, one below)
_PAIR_OFFSET: Final = 0.58
_TRIANGLE_OFFSET: Final = 0.5
_TRIANGLE_DIRECTIONS: Final = ((-math.sqrt(3) / 2, -0.5), (math.sqrt(3) / 2, -0.5), (0.0, 1.0))
# With its labels beside the circles, a Venn diagram's circles take at most half the frame's width (its labels the
# rest, at either side), a label is this far from its circle, and the bottom one of three circles has its label
# below it, in a band as tall as a share of the radius (a little below the circle)
_BESIDE_WIDTH: Final = 0.5
_BESIDE_GAP: Final = int(0.2 * _INCH)
_BOTTOM_BAND: Final = 0.32
_BOTTOM_GAP: Final = 0.06
# How wide the overlap's label is then, as a share of the radius: it may spread over the circles, as their own
# labels are beside them
_BESIDE_OVERLAP: Final = 2.2

# A matrix leaves room around it for the titles at the ends of its axes
_SIDE_TITLE_WIDTH: Final = int(2.1 * _INCH)
_END_TITLE_HEIGHT: Final = int(0.5 * _INCH)
_GAP: Final = int(0.22 * _INCH)
_OVERSHOOT: Final = int(0.1 * _INCH)  # how far the axes' arrows reach beyond the matrix
DOT_DIAMETER: Final = int(0.32 * _INCH)
# A quadrant's label goes at its outer edge, with room for two lines (the dot goes in the rest of the quadrant), and
# so does the dot's name
_QUADRANT_LABEL_HEIGHT: Final = int(0.86 * _INCH)
_DOT_NAME_HEIGHT: Final = int(0.8 * _INCH)
_QUADRANT_NAMES: Final = ("Top left", "Top right", "Bottom left", "Bottom right")

# The margins of a label's text box, inside it: at either side, and above and below its text
_MARGIN_ACROSS: Final = int(0.05 * _INCH)
_MARGIN_DOWN: Final = int(0.03 * _INCH)
SMALLEST: Final = 12  # a label's smallest size, in points
TEMPLATE_FONT: Final = "Calibri"  # the template's (talkgenerator bundles a twin of it, so it's measured everywhere)

Align = Literal["left", "center", "right"]
Anchor = Literal["top", "middle", "bottom"]
_ALIGN: Final = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
_ANCHOR: Final = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


@dataclass(frozen=True)
class Box:
    """A rectangle on a slide, in EMU."""

    left: int
    top: int
    width: int
    height: int

    @classmethod
    def around(cls, x: float, y: float, width: float, height: float) -> Box:
        """The box of this size with its centre at (x, y)."""
        return cls(round(x - width / 2), round(y - height / 2), round(width), round(height))

    @classmethod
    def on_canvas(cls, box: CanvasBox) -> Box:
        """Where a box of a themed deck's canvas (in pixels) is on the slide."""
        return cls(*(round(value * EMU_PER_PIXEL) for value in (box.x, box.y, box.w, box.h)))

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def centre(self) -> tuple[float, float]:
        return self.left + self.width / 2, self.top + self.height / 2


def text_area(box: Box) -> CanvasBox:
    """Where a label's text goes, inside the margins of its text box: on the canvas, in pixels."""
    return CanvasBox(
        x=(box.left + _MARGIN_ACROSS) / EMU_PER_PIXEL,
        y=(box.top + _MARGIN_DOWN) / EMU_PER_PIXEL,
        w=(box.width - 2 * _MARGIN_ACROSS) / EMU_PER_PIXEL,
        h=(box.height - 2 * _MARGIN_DOWN) / EMU_PER_PIXEL,
    )


@dataclass(frozen=True)
class Look:
    """How a diagram looks: the template's colours (TEMPLATE), or a theme's (see look_of)."""

    fills: tuple[RGBColor, ...] = COLOURS  # the circles' or quadrants' colours, in order
    circle_opacity: float = CIRCLE_OPACITY
    quadrant_opacity: float = QUADRANT_OPACITY
    text: RGBColor | None = None  # the labels' colour (None: the template's)
    lines: RGBColor = _AXIS_COLOUR
    punchline: RGBColor = PUNCHLINE_COLOUR  # a matrix's dot, and its name
    outline: RGBColor = _WHITE  # around the dot
    font: str | None = None  # the labels' font (None: the template's, whose letters fitting_size estimates)


TEMPLATE: Final = Look()


def look_of(style: DiagramStyle | None) -> Look:
    """The look of a diagram in a theme's style (or in the template's, without one)."""
    if style is None:
        return TEMPLATE
    return Look(
        fills=tuple(_rgb(fill) for fill in style.fills),
        circle_opacity=style.opacity,
        quadrant_opacity=style.opacity,
        text=_rgb(style.text),
        lines=_rgb(style.lines),
        punchline=_rgb(style.punchline),
        outline=_rgb(style.outline),
        font=style.font,
    )


@dataclass(frozen=True)
class Label:
    """One of a diagram's texts: in its box, at its size (in points), and how it looks."""

    name: str  # its shape's name, such as "Circle 1: Things I love"
    text: str
    box: Box
    size: int
    bold: bool = False
    italic: bool = False
    align: Align = "center"
    anchor: Anchor = "middle"
    colour: Literal["text", "punchline"] = "text"
    reveal: bool = False  # part of the punchline, which can appear on a click


def draw_diagram(
    slide: Any, frame: Box, diagram: VennDiagram | MatrixDiagram, style: DiagramStyle | None = None
) -> list[Any]:
    """Draw the diagram in the frame, in the theme's style (or the template's), and return the shapes of its
    punchline (which appear on a click, if the diagram says so)."""
    look = look_of(style)
    if isinstance(diagram, VennDiagram):
        punchline = draw_venn(slide, frame, diagram, look)
    else:
        punchline = draw_matrix(slide, frame, diagram, look)
    if diagram.reveal == "punchline":
        animation.reveal_shapes(slide, punchline)
    return punchline


def labels(frame: Box, diagram: VennDiagram | MatrixDiagram, font: str | None = None) -> list[Label]:
    """The diagram's texts in the frame, in the order they're drawn, each at the largest size at which it fits: in
    the font, if given (measured), else in the template's (estimated). Labels of one kind share one size."""
    if isinstance(diagram, VennDiagram):
        return _venn_labels(venn_layout_for(frame, diagram, font), diagram, font)
    return _matrix_labels(frame, diagram, font)


# VENN DIAGRAMS


@dataclass(frozen=True)
class VennLayout:
    """Where a Venn diagram's circles and labels go: a circle's centre and radius, the label boxes, and how a circle's
    label lines up in its box (beside its circle, towards it)."""

    centres: tuple[tuple[float, float], ...]
    radius: float
    labels: tuple[Box, ...]  # one per circle
    overlap: Box
    places: tuple[tuple[Align, Anchor], ...]  # one per circle
    beside: bool = False  # the circles' labels are beside them, on the slide's background (not in them)


def venn_layout(frame: Box, circles: int, beside: bool = False) -> VennLayout:
    """The circles as large as fit the frame, around its centre; every circle's label in the part of it that no other
    circle covers, and the overlap's label in the middle, where they all overlap. Or, with the labels beside the
    circles, the circles smaller (see _venn_beside)."""
    if circles not in (2, 3):
        raise ValueError(f"A Venn diagram has two or three circles, not {circles}")
    if beside:
        return _venn_beside(frame, circles)
    x, y = frame.centre
    centres: tuple[tuple[float, float], ...]
    middle: tuple[Align, Anchor] = ("center", "middle")
    if circles == 2:
        offset = _PAIR_OFFSET
        radius = 0.92 * min(frame.height / 2, frame.width / (2 + 2 * offset))
        centres = ((x - offset * radius, y), (x + offset * radius, y))
        # A label goes halfway between its circle's outer edge and the other circle's edge
        labels = tuple(Box.around(x + side * radius, y, 0.8 * radius, 1.1 * radius) for side in (-1, 1))
        overlap = Box.around(x, y, 0.72 * radius, 0.9 * radius)
        return VennLayout(centres, radius, labels, overlap, (middle, middle))

    offset = _TRIANGLE_OFFSET
    radius = 0.94 * min(frame.height / (2 + 1.5 * offset), frame.width / (2 + math.sqrt(3) * offset))
    y -= 0.25 * offset * radius  # (centred as a whole: with one circle below and two on top, they reach further down)
    centres = tuple((x + dx * offset * radius, y + dy * offset * radius) for dx, dy in _TRIANGLE_DIRECTIONS)
    reach = (offset + 0.52) * radius  # a label's centre, from the middle: in the part of its circle that's its own
    labels = tuple(
        Box.around(x + dx * reach, y + dy * reach, 0.85 * radius, 0.6 * radius) for dx, dy in _TRIANGLE_DIRECTIONS
    )
    overlap = Box.around(x, y, 0.9 * radius, 0.6 * radius)
    return VennLayout(centres, radius, labels, overlap, (middle, middle, middle))


def _venn_beside(frame: Box, circles: int) -> VennLayout:
    """The circles smaller, at most half the frame's width, around its centre: every circle's label beside its
    circle, on its outer side (the first circle's on its left, the second's on its right, and the third's, of the
    bottom circle, below it), aligned towards it; and the overlap's label in the middle, wider than in the circles (it
    may spread over them, as their own labels are beside them)."""
    x, y = frame.centre
    centres: tuple[tuple[float, float], ...]
    labels: tuple[Box, ...]
    if circles == 2:
        offset = _PAIR_OFFSET
        radius = min(0.92 * frame.height / 2, _BESIDE_WIDTH * frame.width / (2 + 2 * offset))
        centres = ((x - offset * radius, y), (x + offset * radius, y))
        (left_x, _), (right_x, _) = centres
        left = left_x - radius - _BESIDE_GAP  # (where the labels end, or start, beside the circles)
        right = right_x + radius + _BESIDE_GAP
        labels = (
            Box(frame.left, round(y - 0.45 * radius), round(left - frame.left), round(0.9 * radius)),
            Box(round(right), round(y - 0.45 * radius), round(frame.right - right), round(0.9 * radius)),
        )
        overlap = Box.around(x, y, _BESIDE_OVERLAP * radius, 0.9 * radius)
        return VennLayout(centres, radius, labels, overlap, (("right", "middle"), ("left", "middle")), beside=True)

    offset = _TRIANGLE_OFFSET
    below = _BOTTOM_GAP + _BOTTOM_BAND  # (the bottom circle's label, under it)
    radius = min(
        0.94 * frame.height / (2 + 1.5 * offset + below), _BESIDE_WIDTH * frame.width / (2 + math.sqrt(3) * offset)
    )
    y -= (0.5 * offset + below) / 2 * radius  # (centred as a whole, with the bottom circle's label)
    centres = tuple((x + dx * offset * radius, y + dy * offset * radius) for dx, dy in _TRIANGLE_DIRECTIONS)
    (left_x, left_y), (right_x, right_y), (bottom_x, bottom_y) = centres
    left = left_x - radius - _BESIDE_GAP
    right = right_x + radius + _BESIDE_GAP
    labels = (
        Box(frame.left, round(left_y - 0.4 * radius), round(left - frame.left), round(0.8 * radius)),
        Box(round(right), round(right_y - 0.4 * radius), round(frame.right - right), round(0.8 * radius)),
        Box.around(
            bottom_x, bottom_y + (1 + _BOTTOM_GAP + _BOTTOM_BAND / 2) * radius, 3 * radius, _BOTTOM_BAND * radius
        ),
    )
    overlap = Box.around(x, y, _BESIDE_OVERLAP * radius, 0.6 * radius)
    places: tuple[tuple[Align, Anchor], ...] = (("right", "middle"), ("left", "middle"), ("center", "top"))
    return VennLayout(centres, radius, labels, overlap, places, beside=True)


def venn_layout_for(frame: Box, venn: VennDiagram, font: str | None = None) -> VennLayout:
    """Where the diagram's circles and labels go in the frame: its labels in its circles, if every one of them fits
    its place there at the smallest size (in the font, if given, else in the template's); else beside them."""
    inside = venn_layout(frame, len(venn.circles))
    circles_fit = all(
        fits(text, box, SMALLEST, font=font) for text, box in zip(venn.circles, inside.labels, strict=True)
    )
    if circles_fit and fits(venn.overlap, inside.overlap, SMALLEST, bold=True, font=font):
        return inside
    return venn_layout(frame, len(venn.circles), beside=True)


def labels_beside(frame: Box, diagram: VennDiagram | MatrixDiagram, font: str | None = None) -> bool:
    """Whether the diagram is a Venn diagram with its labels beside its circles (on the slide's background, then)."""
    return isinstance(diagram, VennDiagram) and venn_layout_for(frame, diagram, font).beside


def _venn_labels(layout: VennLayout, venn: VennDiagram, font: str | None) -> list[Label]:
    size = shared_size(venn.circles, layout.labels, 28, font=font)
    found = [
        Label(f"Circle {number}: {text}", text, box, size, align=align, anchor=anchor)
        for number, (text, box, (align, anchor)) in enumerate(
            zip(venn.circles, layout.labels, layout.places, strict=True), 1
        )
    ]
    overlap_size = fitting_size(venn.overlap, layout.overlap, 32, bold=True, font=font)
    found.append(Label(f"Overlap: {venn.overlap}", venn.overlap, layout.overlap, overlap_size, bold=True, reveal=True))
    return found


def draw_venn(slide: Any, frame: Box, venn: VennDiagram, look: Look = TEMPLATE) -> list[Any]:
    """Two or three see-through circles with a label each (in it, or beside it), and the overlap's label (the
    punchline, which this returns) where they all overlap."""
    layout = venn_layout_for(frame, venn, look.font)
    for number, ((x, y), colour) in enumerate(zip(layout.centres, look.fills, strict=False), 1):
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, *_emu(Box.around(x, y, 2 * layout.radius, 2 * layout.radius)))
        circle.name = f"Circle {number}"
        _style(circle, fill=colour, opacity=look.circle_opacity, line=colour)
    punchline = []
    for label in _venn_labels(layout, venn, look.font):
        shape = _add(slide, label, look)
        if label.reveal:
            punchline.append(shape)
    return punchline


# 2×2 MATRICES


@dataclass(frozen=True)
class MatrixLayout:
    """Where a matrix's parts go: its own box, the titles at the ends of its axes, its quadrants and their labels."""

    matrix: Box
    ends: tuple[Box, Box, Box, Box]  # the titles at the left, right, bottom and top ends of the axes
    quadrants: tuple[Box, Box, Box, Box]  # top left, top right, bottom left, bottom right
    labels: tuple[Box, Box, Box, Box]  # the quadrants' labels, in the same order

    @property
    def middle(self) -> tuple[int, int]:
        """Where the axes cross: where the quadrants meet."""
        return self.quadrants[3].left, self.quadrants[3].top

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Where on the slide a point of the matrix is: from its left (0) to its right (1), from its bottom (0) to
        its top (1)."""
        return self.matrix.left + x * self.matrix.width, self.matrix.bottom - y * self.matrix.height

    def axes(self) -> tuple[tuple[str, tuple[float, float], tuple[float, float]], ...]:
        """The axes, each with its name, and where it begins and ends (its arrows reach beyond the matrix)."""
        box, (x, y) = self.matrix, self.middle
        return (
            ("Axis along the bottom", (box.left - _OVERSHOOT, y), (box.right + _OVERSHOOT, y)),
            ("Axis going up", (x, box.bottom + _OVERSHOOT), (x, box.top - _OVERSHOOT)),
        )

    def dot(self, x: float, y: float) -> Box:
        """The box of a dot at (x, y)."""
        return Box.around(*self.point(x, y), DOT_DIAMETER, DOT_DIAMETER)


def matrix_layout(frame: Box) -> MatrixLayout:
    """The matrix in the middle of the frame, with room for the titles at the ends of its axes: those of the axis
    along the bottom on its left and right, those of the axis going up above and below it. A quadrant's label goes at
    its outer edge, so that the dot (nearer the middle) doesn't cover it."""
    side = _SIDE_TITLE_WIDTH + _GAP
    end = _END_TITLE_HEIGHT + _GAP
    matrix = Box(frame.left + side, frame.top + end, frame.width - 2 * side, frame.height - 2 * end)
    x, y = matrix.centre
    ends = (
        Box(frame.left, round(y - 0.75 * _INCH), _SIDE_TITLE_WIDTH, int(1.5 * _INCH)),
        Box(matrix.right + _GAP, round(y - 0.75 * _INCH), _SIDE_TITLE_WIDTH, int(1.5 * _INCH)),
        Box(matrix.left, matrix.bottom + _GAP, matrix.width, _END_TITLE_HEIGHT),
        Box(matrix.left, frame.top, matrix.width, _END_TITLE_HEIGHT),
    )
    half_width, half_height = matrix.width // 2, matrix.height // 2
    quadrants = (
        Box(matrix.left, matrix.top, half_width, half_height),
        Box(matrix.left + half_width, matrix.top, matrix.width - half_width, half_height),
        Box(matrix.left, matrix.top + half_height, half_width, matrix.height - half_height),
        Box(matrix.left + half_width, matrix.top + half_height, matrix.width - half_width, matrix.height - half_height),
    )
    margin = int(0.12 * _INCH)
    labels = []
    for index, quadrant in enumerate(quadrants):
        height = min(_QUADRANT_LABEL_HEIGHT, quadrant.height // 2)
        top = quadrant.top + margin if index < 2 else quadrant.bottom - margin - height
        labels.append(Box(quadrant.left + margin, top, quadrant.width - 2 * margin, height))
    return MatrixLayout(matrix, ends, quadrants, (labels[0], labels[1], labels[2], labels[3]))


def dot_label_box(layout: MatrixLayout, x: float, y: float) -> tuple[Box, Align]:
    """Where the name of a dot at (x, y) goes: beside it, on the side with the most room, and inside the dot's
    quadrant (so it doesn't cross an axis). Its text aligns towards the dot."""
    dot_x, dot_y = layout.point(x, y)
    middle_x, middle_y = layout.middle
    box = layout.matrix
    left_edge, right_edge = (box.left, middle_x) if dot_x < middle_x else (middle_x, box.right)
    top_edge, bottom_edge = (box.top, middle_y) if dot_y < middle_y else (middle_y, box.bottom)
    margin = int(0.08 * _INCH)
    reach = DOT_DIAMETER / 2 + margin
    room_left, room_right = dot_x - reach - left_edge - margin, right_edge - margin - (dot_x + reach)
    height = min(_DOT_NAME_HEIGHT, bottom_edge - top_edge - 2 * margin)
    top = min(max(dot_y - height / 2, top_edge + margin), bottom_edge - margin - height)
    if room_right >= room_left:
        width = max(room_right, 0.5 * _INCH)
        return Box(round(dot_x + reach), round(top), round(width), round(height)), "left"
    width = max(room_left, 0.5 * _INCH)
    return Box(round(dot_x - reach - width), round(top), round(width), round(height)), "right"


def _matrix_labels(frame: Box, matrix: MatrixDiagram, font: str | None) -> list[Label]:
    layout = matrix_layout(frame)
    ends = (matrix.x_left, matrix.x_right, matrix.y_bottom, matrix.y_top)
    places: tuple[tuple[str, Align, Anchor], ...] = (
        ("Left end", "right", "middle"),
        ("Right end", "left", "middle"),
        ("Bottom end", "center", "top"),
        ("Top end", "center", "bottom"),
    )
    size = shared_size(ends, layout.ends, 22, font=font)
    found = [
        Label(f"{name}: {title}", title, box, size, italic=True, align=align, anchor=anchor)
        for title, box, (name, align, anchor) in zip(ends, layout.ends, places, strict=True)
    ]
    quadrant_labels = (matrix.top_left, matrix.top_right, matrix.bottom_left, matrix.bottom_right)
    size = shared_size(quadrant_labels, layout.labels, 26, bold=True, font=font)
    found += [
        Label(f"{name} quadrant: {text}", text, box, size, bold=True, anchor="top" if index < 2 else "bottom")
        for index, (text, box, name) in enumerate(zip(quadrant_labels, layout.labels, _QUADRANT_NAMES, strict=True))
    ]
    name_box, align = dot_label_box(layout, matrix.dot_x, matrix.dot_y)
    size = fitting_size(matrix.dot, name_box, 24, bold=True, font=font)
    found.append(
        Label(f"Dot: {matrix.dot}", matrix.dot, name_box, size, bold=True, align=align, colour="punchline", reveal=True)
    )
    return found


def draw_matrix(slide: Any, frame: Box, matrix: MatrixDiagram, look: Look = TEMPLATE) -> list[Any]:
    """Four see-through quadrants with a label each, two axes crossing in the middle with a title at each end, and a
    dot with its name (the punchline: this returns its shapes)."""
    layout = matrix_layout(frame)
    for quadrant, colour, name in zip(layout.quadrants, look.fills, _QUADRANT_NAMES, strict=True):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *_emu(quadrant))
        shape.name = f"{name} quadrant"
        _style(shape, fill=colour, opacity=look.quadrant_opacity)
    for name, begin, end in layout.axes():
        axis = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, *(Emu(round(value)) for value in (*begin, *end)))
        axis.name = name
        _arrow(axis, look.lines)

    texts = _matrix_labels(frame, matrix, look.font)
    for label in texts:
        if not label.reveal:
            _add(slide, label, look)
    dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, *_emu(layout.dot(matrix.dot_x, matrix.dot_y)))
    dot.name = "Dot"
    _style(dot, fill=look.punchline, line=look.outline)
    return [dot, *(_add(slide, label, look) for label in texts if label.reveal)]


# SHAPES AND LABELS


def _add(slide: Any, label: Label, look: Look) -> Any:
    colour = look.punchline if label.colour == "punchline" else look.text
    return add_label(
        slide,
        label.box,
        label.text,
        label.size,
        bold=label.bold,
        italic=label.italic,
        colour=colour,
        align=_ALIGN[label.align],
        anchor=_ANCHOR[label.anchor],
        name=label.name,
        font=look.font,
    )


def add_label(
    slide: Any,
    box: Box,
    text: str,
    size: int,
    *,
    bold: bool = False,
    italic: bool = False,
    colour: RGBColor | None = None,
    align: PP_ALIGN = PP_ALIGN.CENTER,
    anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
    name: str | None = None,
    font: str | None = None,
) -> Any:
    """A text box with the text in it, wrapped, at a size in points (see fitting_size), in the font (if given)."""
    shape = slide.shapes.add_textbox(*_emu(box))
    if name:
        shape.name = name[:60]
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Emu(_MARGIN_ACROSS)
    frame.margin_top = frame.margin_bottom = Emu(_MARGIN_DOWN)
    frame.auto_size = MSO_AUTO_SIZE.NONE  # (python-pptx's text boxes grow with their text; the font size fits it)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if font is not None:
        run.font.name = font
    if colour is not None:
        run.font.color.rgb = colour
    return shape


def shared_size(
    texts: Sequence[str], boxes: Sequence[Box], largest: int, *, bold: bool = False, font: str | None = None
) -> int:
    """The size at which every text fits its box (labels that are alike look alike: one long one makes them all
    smaller)."""
    return min(fitting_size(text, box, largest, bold=bold, font=font) for text, box in zip(texts, boxes, strict=True))


def fitting_size(
    text: str, box: Box, largest: int, *, bold: bool = False, smallest: int = SMALLEST, font: str | None = None
) -> int:
    """The largest font size, in points, at which the text fits the box when wrapped between its words. In a font
    (a theme's), it's measured, as the layout engine measures texts (talkgenerator.design.fit). Else, it's estimated
    for the template's font (see fits). PowerPoint doesn't shrink text to fit until it's edited, so the size has to
    be right from the start."""
    if font is not None:
        area = text_area(box)
        fitted = fit.fit(
            text, area.w, area.h, font, 2 * largest, 2 * smallest, bold
        )  # (a canvas pixel is half a point)
        return max(smallest, round(fitted.size / 2))
    for size in range(largest, smallest, -1):
        if fits(text, box, size, bold=bold):
            return size
    return smallest


def fits(text: str, box: Box, size: int, *, bold: bool = False, font: str | None = None) -> bool:
    """Whether the text fits the box at the size (in points), wrapped between its words. In a font, it's measured.
    Else, the template's font (Calibri): its lines are estimated by the width of an average letter, about half the
    font size (a little more in bold), and every word is measured, as PowerPoint breaks a word that's wider than the
    line in the middle of it."""
    area = text_area(box)
    if font is not None:
        return fit.fit(text, area.w, area.h, font, 2 * size, 2 * size, bold).fits
    width = box.width / _INCH - 0.1  # (the text box's margins)
    height = box.height / _INCH - 0.06
    words = text.split()
    letters = max(1, int(width / (size / 72 * (0.55 if bold else 0.5))))
    if _lines(words, letters) * size / 72 * 1.2 > height:
        return False
    return all(fonts.text_width(word, TEMPLATE_FONT, 2 * size, bold) <= area.w for word in words)


def _lines(words: list[str], letters: int) -> int:
    """How many lines the words take, wrapped between them, with at most this many letters on a line (a longer word
    is counted as broken over lines, though it doesn't fit: see fits)."""
    lines, used = 0, letters  # (so the first word starts a line)
    for word in words:
        if len(word) > letters:
            lines += math.ceil(len(word) / letters)
            used = len(word) % letters or letters
        elif used + 1 + len(word) <= letters:
            used += 1 + len(word)
        else:
            lines += 1
            used = len(word)
    return max(lines, 1)


def _style(shape: Any, *, fill: RGBColor, opacity: float = 1.0, line: RGBColor | None = None) -> None:
    """Fill the shape with a colour (see-through below an opacity of 1), with an outline in a colour or none, and
    without the theme's shape style (which adds a shadow)."""
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if opacity < 1:  # (an alpha in the colour: python-pptx has no setting for it)
        colour = shape._element.spPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
        colour.append(parse_xml(f'<a:alpha {nsdecls("a")} val="{round(opacity * 100000)}"/>'))
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(2)
    _drop_style(shape)


def _arrow(connector: Any, colour: RGBColor = _AXIS_COLOUR) -> None:
    """A line with an arrowhead at both ends."""
    connector.line.color.rgb = colour
    connector.line.width = Pt(2.5)
    outline = connector.line._get_or_add_ln()
    for end in ("a:headEnd", "a:tailEnd"):
        outline.append(parse_xml(f'<{end} {nsdecls("a")} type="triangle" w="med" len="med"/>'))
    _drop_style(connector)


def _drop_style(shape: Any) -> None:
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)


def _emu(box: Box) -> tuple[Emu, Emu, Emu, Emu]:
    return Emu(box.left), Emu(box.top), Emu(box.width), Emu(box.height)


def _rgb(value: str) -> RGBColor:
    colour: RGBColor = RGBColor.from_string(value.lstrip("#"))
    return colour
