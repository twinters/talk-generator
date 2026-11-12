"""The geometry of a theme's shapes (see talkgenerator.models.deck.ShapeElement): polygons in a box, such as stars,
pennants and hearts, as shares of the box (from (0, 0), its top left corner, to (1, 1), its bottom right), and where a
shape is on the canvas once it's turned around its middle. Every renderer draws a polygon from the same corners
(PowerPoint as a freeform, a browser as a clip path, previews with Pillow), and the design checks use them to tell
what's behind a text.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from talkgenerator.models.deck import Box, ShapeElement

Point = tuple[float, float]
Points = tuple[Point, ...]

# How many corners an ellipse is taken to have, where one is needed as a polygon (by the design checks)
ELLIPSE_CORNERS: Final = 48


def _rounded(points: Sequence[Point]) -> Points:
    """The points, rounded to four decimals (so that a deck's JSON stays short and the same everywhere)."""
    return tuple((round(x, 4), round(y, 4)) for x, y in points)


def star(spikes: int = 5, inner: float = 0.45) -> Points:
    """A star with that many spikes, the first pointing up; its inner corners this far out (from 0, the middle, to 1,
    as far as its spikes)."""
    corners = []
    for index in range(2 * spikes):
        reach = 0.5 if index % 2 == 0 else 0.5 * inner
        angle = -math.pi / 2 + math.pi * index / spikes
        corners.append((0.5 + reach * math.cos(angle), 0.5 + reach * math.sin(angle)))
    return _rounded(_fill_box(corners))


def burst(spikes: int = 14, inner: float = 0.72) -> Points:
    """A starburst (a comic's "POW!", a sale sticker's), with many short spikes."""
    return star(spikes, inner)


def heart() -> Points:
    """A heart, from the classic curve (16 sin³t, 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t)."""
    corners = []
    for index in range(40):
        t = 2 * math.pi * index / 40
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        corners.append((x, y))
    return _rounded(_fill_box(corners))


def triangle() -> Points:
    """A triangle pointing up."""
    return ((0.5, 0.0), (1.0, 1.0), (0.0, 1.0))


def pennant() -> Points:
    """A bunting's flag: a triangle hanging from its top edge."""
    return ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))


def diamond() -> Points:
    return ((0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 0.5))


def arrow() -> Points:
    """An arrow pointing right."""
    return ((0.0, 0.32), (0.58, 0.32), (0.58, 0.0), (1.0, 0.5), (0.58, 1.0), (0.58, 0.68), (0.0, 0.68))


def blob(wobbles: Sequence[tuple[float, float]], corners: int = 28) -> Points:
    """A rounded, irregular blob, as a drop of ink spreads (an inkblot's: D78): a circle whose radius wobbles, by each
    of the wobbles (an amount, as a share of the radius, and where it starts, as a share of a turn), the first one
    twice around, the next three times, and so on, stretched to fill its box."""
    points = []
    for index in range(corners):
        angle = 2 * math.pi * index / corners
        reach = 1 + sum(
            amount * math.cos((number + 2) * angle + 2 * math.pi * start)
            for number, (amount, start) in enumerate(wobbles)
        )
        points.append((max(reach, 0.2) * math.cos(angle), max(reach, 0.2) * math.sin(angle)))
    return _rounded(_fill_box(points))


def mirrored(points: Sequence[Point]) -> Points:
    """A polygon's corners, mirrored left to right in its box (an inkblot's other half)."""
    return tuple((round(1.0 - x, 4), y) for x, y in points)


def slanted(by: float = 0.12) -> Points:
    """A parallelogram leaning right: its top edge this share of its width further right than its bottom edge."""
    return ((by, 0.0), (1.0, 0.0), (1.0 - by, 1.0), (0.0, 1.0))


def tail(left: bool = True) -> Points:
    """A speech bubble's tail, hanging from the bubble at its top edge and pointing down to one side."""
    return ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)) if left else ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))


def wave(waves: float = 1.5, depth: float = 0.35, steps: int = 36) -> Points:
    """A band whose top edge is a wave (from its left edge to its right, this many waves, this deep, as a share of
    its height) and whose bottom edge is straight: a 1990s swoosh along a slide's foot."""
    top = [
        (index / steps, depth / 2 * (1 - math.cos(2 * math.pi * waves * index / steps))) for index in range(steps + 1)
    ]
    return _rounded([*top, (1.0, 1.0), (0.0, 1.0)])


def scallop(bumps: int = 12, depth: float = 0.14, steps: int = 6) -> Points:
    """A circle whose edge is that many round bumps, this deep (as a share of its radius): a rosette's, a paper
    flower's."""
    corners = []
    for index in range(bumps * steps):
        angle = 2 * math.pi * index / (bumps * steps)
        reach = 0.5 * (1 - depth + depth * abs(math.cos(bumps * angle / 2)))
        corners.append((0.5 + reach * math.sin(angle), 0.5 - reach * math.cos(angle)))
    return _rounded(_fill_box(corners))


def arch(inner: float = 0.6, steps: int = 24) -> Points:
    """The top half of a ring (a rainbow's band): its box twice as wide as it's tall, its hole this wide (a share of
    its width)."""
    turns = [math.pi * step / steps for step in range(steps + 1)]
    outer = [(0.5 - 0.5 * math.cos(angle), 1 - math.sin(angle)) for angle in turns]
    hole = [(0.5 + 0.5 * inner * math.cos(angle), 1 - inner * math.sin(angle)) for angle in turns]
    return _rounded([*outer, *hole])


def pinked(teeth: int = 12, depth: float = 0.35) -> Points:
    """A strip with a straight top edge and a bottom edge cut in zigzags, as pinking shears cut it: that many teeth,
    this deep (a share of its height)."""
    bottom = [(1 - index / (2 * teeth), 1.0 if index % 2 == 0 else 1 - depth) for index in range(2 * teeth + 1)]
    return _rounded([(0.0, 0.0), (1.0, 0.0), *bottom])


def leaf(steps: int = 12) -> Points:
    """A leaf (two arcs meeting at its ends), lying from its left end to its right."""
    top = [(step / steps, 0.5 - 0.5 * math.sin(math.pi * step / steps)) for step in range(steps + 1)]
    bottom = [(1 - step / steps, 0.5 + 0.5 * math.sin(math.pi * step / steps)) for step in range(1, steps)]
    return _rounded([*top, *bottom])


def ribbon() -> Points:
    """A rosette's ribbon tail, hanging down, with a notch cut into its end."""
    return ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 0.8), (0.0, 1.0))


def stroke(line: Sequence[Point], width: float) -> tuple[Box, Points]:
    """A line through the points (on the canvas) as wide as width (in canvas pixels): its box, and the polygon of
    its outline in that box (each corner mitred, up to twice the width). For a hand-drawn underline or a squiggle."""
    half = width / 2
    left, right = [], []
    for index, (x, y) in enumerate(line):
        before = line[index - 1] if index > 0 else None
        after = line[index + 1] if index < len(line) - 1 else None
        normals = [_normal(start, end) for start, end in ((before, (x, y)), ((x, y), after)) if start and end]
        nx = sum(normal[0] for normal in normals)
        ny = sum(normal[1] for normal in normals)
        length = math.hypot(nx, ny) or 1.0
        nx, ny = nx / length, ny / length
        # (a mitre: further out where the line turns, as far as twice the width)
        cosine = max(0.5, abs(nx * normals[0][0] + ny * normals[0][1])) if normals else 1.0
        reach = half / cosine
        left.append((x + nx * reach, y + ny * reach))
        right.append((x - nx * reach, y - ny * reach))
    edge = [*left, *reversed(right)]
    x0, y0 = min(x for x, _ in edge), min(y for _, y in edge)
    x1, y1 = max(x for x, _ in edge), max(y for _, y in edge)
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    return Box(x=x0, y=y0, w=w, h=h), _rounded([((x - x0) / w, (y - y0) / h) for x, y in edge])


def squiggle(x: float, y: float, width: float, amplitude: float, waves: float, steps: int = 32) -> list[Point]:
    """A wavy line from (x, y), this wide, going up and down by amplitude, this many times."""
    return [
        (x + width * index / steps, y + amplitude * math.sin(2 * math.pi * waves * index / steps))
        for index in range(steps + 1)
    ]


def arc(cx: float, cy: float, rx: float, ry: float, start: float, end: float, steps: int = 24) -> list[Point]:
    """Points along an ellipse around (cx, cy), from one angle to another (in degrees, clockwise from its right, as
    the canvas's y goes down): a hand-drawn circle's stroke, a smile."""
    return [
        (
            cx + rx * math.cos(math.radians(start + (end - start) * index / steps)),
            cy + ry * math.sin(math.radians(start + (end - start) * index / steps)),
        )
        for index in range(steps + 1)
    ]


def spiral(cx: float, cy: float, radius: float, turns: float = 2.5, steps: int = 60) -> list[Point]:
    """A spiral from (cx, cy) out to radius, that many turns (a doodle in a notebook's margin)."""
    return [
        (
            cx + radius * index / steps * math.cos(2 * math.pi * turns * index / steps),
            cy + radius * index / steps * math.sin(2 * math.pi * turns * index / steps),
        )
        for index in range(1, steps + 1)
    ]


def _normal(start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    return -dy / length, dx / length


def _fill_box(corners: Sequence[Point]) -> list[Point]:
    """The corners stretched to fill the box from (0, 0) to (1, 1)."""
    x0, y0 = min(x for x, _ in corners), min(y for _, y in corners)
    x1, y1 = max(x for x, _ in corners), max(y for _, y in corners)
    return [((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)) for x, y in corners]


# WHERE A SHAPE IS ON THE CANVAS


def turn(point: Point, around: Point, degrees: float) -> Point:
    """The point turned the degrees (clockwise, on the canvas, whose y goes down) around another."""
    if not degrees:
        return point
    angle = math.radians(degrees)
    dx, dy = point[0] - around[0], point[1] - around[1]
    return around[0] + dx * math.cos(angle) - dy * math.sin(angle), around[1] + dx * math.sin(angle) + dy * math.cos(
        angle
    )


def outline(shape: ShapeElement) -> list[Point]:
    """The shape's corners on the canvas, turned as it is (an ellipse's as a polygon of many corners)."""
    box = shape.box
    if shape.shape == "polygon" and shape.points:
        corners = [(box.x + x * box.w, box.y + y * box.h) for x, y in shape.points]
    elif shape.shape == "ellipse":
        corners = [
            (
                box.x + box.w / 2 * (1 + math.cos(2 * math.pi * index / ELLIPSE_CORNERS)),
                box.y + box.h / 2 * (1 + math.sin(2 * math.pi * index / ELLIPSE_CORNERS)),
            )
            for index in range(ELLIPSE_CORNERS)
        ]
    elif shape.corner > 0:  # (each rounded corner as a few points along its arc)
        radius = min(shape.corner, box.w / 2, box.h / 2)
        corners = []
        for (cx, cy), start in (
            ((box.x + box.w - radius, box.y + radius), -90),
            ((box.x + box.w - radius, box.y + box.h - radius), 0),
            ((box.x + radius, box.y + box.h - radius), 90),
            ((box.x + radius, box.y + radius), 180),
        ):
            for step in range(7):
                angle = math.radians(start + 15 * step)
                corners.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    else:
        corners = [(box.x, box.y), (box.x + box.w, box.y), (box.x + box.w, box.y + box.h), (box.x, box.y + box.h)]
    middle = (box.x + box.w / 2, box.y + box.h / 2)
    return [turn(corner, middle, shape.rotation) for corner in corners]


def bounds(shape: ShapeElement) -> Box:
    """The box around the shape as it's drawn, turned."""
    if not shape.rotation:
        return shape.box
    corners = outline(shape)
    x0, y0 = min(x for x, _ in corners), min(y for _, y in corners)
    x1, y1 = max(x for x, _ in corners), max(y for _, y in corners)
    return Box(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def contains(shape: ShapeElement, point: Point) -> bool:
    """Whether the point is in the shape as it's drawn (in its fill)."""
    corners = outline(shape)
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(corners, [*corners[1:], corners[0]], strict=True):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def covers(shape: ShapeElement, box: Box) -> bool:
    """Whether the shape (its fill) covers the whole box: all its corners, and its middle."""
    points = [
        (box.x, box.y),
        (box.x + box.w, box.y),
        (box.x, box.y + box.h),
        (box.x + box.w, box.y + box.h),
        (box.x + box.w / 2, box.y + box.h / 2),
    ]
    return all(contains(shape, point) for point in points)


def touches(shape: ShapeElement, box: Box) -> bool:
    """Whether the shape as it's drawn (turned) reaches into the box: one of its corners in the box, one of the box's
    corners in the shape, or two of their edges crossing. (Edges that only meet don't count: the box is taken half
    a pixel smaller.)"""
    box = Box(x=box.x + 0.5, y=box.y + 0.5, w=max(0.0, box.w - 1), h=max(0.0, box.h - 1))
    corners = outline(shape)
    if any(box.x <= x <= box.x + box.w and box.y <= y <= box.y + box.h for x, y in corners):
        return True
    box_corners = [(box.x, box.y), (box.x + box.w, box.y), (box.x + box.w, box.y + box.h), (box.x, box.y + box.h)]
    if any(contains(shape, corner) for corner in box_corners):
        return True
    edges = list(zip(corners, [*corners[1:], corners[0]], strict=True))
    box_edges = list(zip(box_corners, [*box_corners[1:], box_corners[0]], strict=True))
    return any(_cross(a, b, c, d) for a, b in edges for c, d in box_edges)


def _cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    def side(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return (side(a, b, c) > 0) != (side(a, b, d) > 0) and (side(c, d, a) > 0) != (side(c, d, b) > 0)
