"""Diagrams drawn as PowerPoint shapes: Venn diagrams and 2×2 matrices.

A deck holds only a diagram's texts and where its dot goes (`VennDiagram`, `MatrixDiagram`), so a diagram needs no
image source and looks the same wherever the deck is drawn. In PowerPoint, it fills the frame where the classic
template's title-and-content slide has its content: circles, rectangles and lines, with text boxes for the labels.
python-pptx can't make shapes see-through, so the circles' and quadrants' colours get their transparency in the
fill's XML.

A diagram whose `reveal` is "punchline" shows its punchline (a Venn diagram's overlap, a matrix's dot and its name) on
a click (see `talkgenerator.render.animation`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from talkgenerator.models.deck import MatrixDiagram, VennDiagram
from talkgenerator.render import animation
from talkgenerator.render.charts import PUNCHLINE_COLOUR

_INCH: Final = 914400  # EMU

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

# A matrix leaves room around it for the titles at the ends of its axes
_SIDE_TITLE_WIDTH: Final = int(2.1 * _INCH)
_END_TITLE_HEIGHT: Final = int(0.5 * _INCH)
_GAP: Final = int(0.22 * _INCH)
_OVERSHOOT: Final = int(0.1 * _INCH)  # how far the axes' arrows reach beyond the matrix
_DOT_DIAMETER: Final = int(0.32 * _INCH)
# A quadrant's label goes at its outer edge, with room for two lines (the dot goes in the rest of the quadrant), and
# so does the dot's name
_QUADRANT_LABEL_HEIGHT: Final = int(0.86 * _INCH)
_DOT_NAME_HEIGHT: Final = int(0.8 * _INCH)


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

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def centre(self) -> tuple[float, float]:
        return self.left + self.width / 2, self.top + self.height / 2


def draw_diagram(slide: Any, frame: Box, diagram: VennDiagram | MatrixDiagram) -> list[Any]:
    """Draw the diagram in the frame, and return the shapes of its punchline (which appear on a click, if the diagram
    says so)."""
    if isinstance(diagram, VennDiagram):
        punchline = draw_venn(slide, frame, diagram)
    else:
        punchline = draw_matrix(slide, frame, diagram)
    if diagram.reveal == "punchline":
        animation.reveal_shapes(slide, punchline)
    return punchline


# VENN DIAGRAMS


@dataclass(frozen=True)
class VennLayout:
    """Where a Venn diagram's circles and labels go: a circle's centre and radius, and the label boxes."""

    centres: tuple[tuple[float, float], ...]
    radius: float
    labels: tuple[Box, ...]  # one per circle
    overlap: Box


def venn_layout(frame: Box, circles: int) -> VennLayout:
    """The circles as large as fit the frame, around its centre; every circle's label in the part of it that no other
    circle covers, and the overlap's label in the middle, where they all overlap."""
    if circles not in (2, 3):
        raise ValueError(f"A Venn diagram has two or three circles, not {circles}")
    x, y = frame.centre
    centres: tuple[tuple[float, float], ...]
    if circles == 2:
        offset = _PAIR_OFFSET
        radius = 0.92 * min(frame.height / 2, frame.width / (2 + 2 * offset))
        centres = ((x - offset * radius, y), (x + offset * radius, y))
        # A label goes halfway between its circle's outer edge and the other circle's edge
        labels = tuple(Box.around(x + side * radius, y, 0.8 * radius, 1.1 * radius) for side in (-1, 1))
        overlap = Box.around(x, y, 0.72 * radius, 0.9 * radius)
        return VennLayout(centres, radius, labels, overlap)

    offset = _TRIANGLE_OFFSET
    radius = 0.94 * min(frame.height / (2 + 1.5 * offset), frame.width / (2 + math.sqrt(3) * offset))
    y -= 0.25 * offset * radius  # (centred as a whole: with one circle below and two on top, they reach further down)
    centres = tuple((x + dx * offset * radius, y + dy * offset * radius) for dx, dy in _TRIANGLE_DIRECTIONS)
    reach = (offset + 0.52) * radius  # a label's centre, from the middle: in the part of its circle that's its own
    labels = tuple(
        Box.around(x + dx * reach, y + dy * reach, 0.85 * radius, 0.6 * radius) for dx, dy in _TRIANGLE_DIRECTIONS
    )
    overlap = Box.around(x, y, 0.9 * radius, 0.6 * radius)
    return VennLayout(centres, radius, labels, overlap)


def draw_venn(slide: Any, frame: Box, venn: VennDiagram) -> list[Any]:
    """Two or three see-through circles with a label each, and the overlap's label (the punchline, which this returns)
    where they all overlap."""
    layout = venn_layout(frame, len(venn.circles))
    for number, ((x, y), colour) in enumerate(zip(layout.centres, COLOURS, strict=False), 1):
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, *_emu(Box.around(x, y, 2 * layout.radius, 2 * layout.radius)))
        circle.name = f"Circle {number}"
        _style(circle, fill=colour, opacity=CIRCLE_OPACITY, line=colour)
    size = shared_size(venn.circles, layout.labels, 28)
    for number, (label, box) in enumerate(zip(venn.circles, layout.labels, strict=True), 1):
        add_label(slide, box, label, size, name=f"Circle {number}: {label}")
    overlap_size = fitting_size(venn.overlap, layout.overlap, 32, bold=True)
    overlap = add_label(slide, layout.overlap, venn.overlap, overlap_size, bold=True, name=f"Overlap: {venn.overlap}")
    return [overlap]


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


def dot_label_box(layout: MatrixLayout, x: float, y: float) -> tuple[Box, PP_ALIGN]:
    """Where the name of a dot at (x, y) goes: beside it, on the side with the most room, and inside the dot's
    quadrant (so it doesn't cross an axis). Its text aligns towards the dot."""
    dot_x, dot_y = layout.point(x, y)
    middle_x, middle_y = layout.middle
    box = layout.matrix
    left_edge, right_edge = (box.left, middle_x) if dot_x < middle_x else (middle_x, box.right)
    top_edge, bottom_edge = (box.top, middle_y) if dot_y < middle_y else (middle_y, box.bottom)
    margin = int(0.08 * _INCH)
    reach = _DOT_DIAMETER / 2 + margin
    room_left, room_right = dot_x - reach - left_edge - margin, right_edge - margin - (dot_x + reach)
    height = min(_DOT_NAME_HEIGHT, bottom_edge - top_edge - 2 * margin)
    top = min(max(dot_y - height / 2, top_edge + margin), bottom_edge - margin - height)
    if room_right >= room_left:
        width = max(room_right, 0.5 * _INCH)
        return Box(round(dot_x + reach), round(top), round(width), round(height)), PP_ALIGN.LEFT
    width = max(room_left, 0.5 * _INCH)
    return Box(round(dot_x - reach - width), round(top), round(width), round(height)), PP_ALIGN.RIGHT


def draw_matrix(slide: Any, frame: Box, matrix: MatrixDiagram) -> list[Any]:
    """Four see-through quadrants with a label each, two axes crossing in the middle with a title at each end, and a
    dot with its name (the punchline: this returns its shapes)."""
    layout = matrix_layout(frame)
    quadrant_labels = (matrix.top_left, matrix.top_right, matrix.bottom_left, matrix.bottom_right)
    names = ("Top left", "Top right", "Bottom left", "Bottom right")
    for quadrant, colour, name in zip(layout.quadrants, COLOURS, names, strict=True):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *_emu(quadrant))
        shape.name = f"{name} quadrant"
        _style(shape, fill=colour, opacity=QUADRANT_OPACITY)

    box, (x, y) = layout.matrix, layout.middle
    for name, begin, end in (
        ("Axis along the bottom", (box.left - _OVERSHOOT, y), (box.right + _OVERSHOOT, y)),
        ("Axis going up", (x, box.bottom + _OVERSHOOT), (x, box.top - _OVERSHOOT)),
    ):
        axis = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, *(Emu(round(value)) for value in (*begin, *end)))
        axis.name = name
        _arrow(axis)

    ends = (matrix.x_left, matrix.x_right, matrix.y_bottom, matrix.y_top)
    alignments = (PP_ALIGN.RIGHT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER)
    anchors = (MSO_ANCHOR.MIDDLE, MSO_ANCHOR.MIDDLE, MSO_ANCHOR.TOP, MSO_ANCHOR.BOTTOM)
    size = shared_size(ends, layout.ends, 22)
    for title, end_box, align, anchor, name in zip(
        ends, layout.ends, alignments, anchors, ("Left end", "Right end", "Bottom end", "Top end"), strict=True
    ):
        add_label(slide, end_box, title, size, align=align, anchor=anchor, italic=True, name=f"{name}: {title}")
    size = shared_size(quadrant_labels, layout.labels, 26, bold=True)
    for index, (label, label_box, name) in enumerate(zip(quadrant_labels, layout.labels, names, strict=True)):
        anchor = MSO_ANCHOR.TOP if index < 2 else MSO_ANCHOR.BOTTOM
        add_label(slide, label_box, label, size, bold=True, anchor=anchor, name=f"{name} quadrant: {label}")

    dot_x, dot_y = layout.point(matrix.dot_x, matrix.dot_y)
    dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, *_emu(Box.around(dot_x, dot_y, _DOT_DIAMETER, _DOT_DIAMETER)))
    dot.name = "Dot"
    _style(dot, fill=PUNCHLINE_COLOUR, line=_WHITE)
    name_box, align = dot_label_box(layout, matrix.dot_x, matrix.dot_y)
    size = fitting_size(matrix.dot, name_box, 24, bold=True)
    name = add_label(
        slide, name_box, matrix.dot, size, bold=True, colour=PUNCHLINE_COLOUR, align=align, name=f"Dot: {matrix.dot}"
    )
    return [dot, name]


# SHAPES AND LABELS


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
) -> Any:
    """A text box with the text in it, wrapped, at a size in points (see fitting_size)."""
    shape = slide.shapes.add_textbox(*_emu(box))
    if name:
        shape.name = name[:60]
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Emu(int(0.05 * _INCH))
    frame.margin_top = frame.margin_bottom = Emu(int(0.03 * _INCH))
    frame.auto_size = MSO_AUTO_SIZE.NONE  # (python-pptx's text boxes grow with their text; the font size fits it)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if colour is not None:
        run.font.color.rgb = colour
    return shape


def shared_size(texts: Sequence[str], boxes: Sequence[Box], largest: int, *, bold: bool = False) -> int:
    """The size at which every text fits its box (labels that are alike look alike: one long one makes them all
    smaller)."""
    return min(fitting_size(text, box, largest, bold=bold) for text, box in zip(texts, boxes, strict=True))


def fitting_size(text: str, box: Box, largest: int, *, bold: bool = False, smallest: int = 12) -> int:
    """The largest font size, in points, at which the text seems to fit the box when wrapped between its words: by
    the width of an average letter of the template's font (Calibri), about half the font size (a little more in
    bold). PowerPoint doesn't shrink text to fit until it's edited, so the size has to be right from the start."""
    width = box.width / _INCH - 0.1  # (the text box's margins)
    height = box.height / _INCH - 0.06
    words = text.split()
    for size in range(largest, smallest, -1):
        letters = max(1, int(width / (size / 72 * (0.55 if bold else 0.5))))
        if _lines(words, letters) * size / 72 * 1.2 <= height:
            return size
    return smallest


def _lines(words: list[str], letters: int) -> int:
    """How many lines the words take, wrapped between them, with at most this many letters on a line (a longer word
    is broken over lines)."""
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


def _arrow(connector: Any) -> None:
    """A dark line with an arrowhead at both ends."""
    connector.line.color.rgb = _AXIS_COLOUR
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
