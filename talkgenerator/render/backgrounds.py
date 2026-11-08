"""A slide's background as a picture: its colour (or gradient) and the pattern over it (lines, a grid or dots: see
talkgenerator.models.theme.BackgroundPattern), drawn with Pillow. Previews draw it so, and so does PowerPoint, as the
slide's background picture, the same for every slide of a deck (a .pptx keeps it once). A browser draws the pattern
with CSS gradients, from the same numbers.
"""

from __future__ import annotations

import io
import math
from functools import cache

from PIL import Image, ImageChops, ImageDraw

from talkgenerator.design.engine import HEIGHT, WIDTH
from talkgenerator.models.deck import SlideBackground
from talkgenerator.models.theme import BackgroundPattern


def paint(canvas: Image.Image, top: str, bottom: str | None, pattern: BackgroundPattern | None, scale: float) -> None:
    """Paint the background on the canvas (RGBA, the slide at the scale): a colour, or a gradient from the top colour
    down to the bottom one, and the pattern over it."""
    if bottom is None:
        canvas.paste(top, (0, 0, canvas.width, canvas.height))
    else:
        draw = ImageDraw.Draw(canvas)
        first, last = _rgb(top), _rgb(bottom)
        for y in range(canvas.height):
            share = y / max(1, canvas.height - 1)
            draw.line(
                [(0, y), (canvas.width, y)],
                fill=tuple(round(a + (b - a) * share) for a, b in zip(first, last, strict=True)),
            )
    if pattern is not None:
        canvas.alpha_composite(pattern_layer(pattern, canvas.size, scale))


def pattern_layer(pattern: BackgroundPattern, size: tuple[int, int], scale: float) -> Image.Image:
    """The pattern on a transparent layer of the size (the slide at the scale). A line or dot thinner than a pixel at
    the scale is drawn a pixel thick and that much fainter, so a small preview looks as light as the slide."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    red, green, blue = _rgb(pattern.color)
    spacing = max(2.0, pattern.spacing)

    def paint_band(thickness: float) -> tuple[float, tuple[int, int, int, int]]:
        pixels = thickness * scale
        alpha = pattern.opacity * min(1.0, pixels)
        return max(1.0, pixels), (red, green, blue, round(255 * alpha))

    if pattern.kind in ("lines", "grid"):
        for index in range(math.ceil((HEIGHT - pattern.offset) / spacing) + 1):
            y = pattern.offset + index * spacing
            thickness = pattern.size * (2 if pattern.major and index % pattern.major == 0 else 1)
            pixels, fill = paint_band(thickness)
            top = round(y * scale)
            draw.rectangle((0, top, size[0], top + round(pixels) - 1), fill=fill)
    if pattern.kind == "grid":
        for index in range(math.ceil((WIDTH - pattern.offset) / spacing) + 1):
            x = pattern.offset + index * spacing
            thickness = pattern.size * (2 if pattern.major and index % pattern.major == 0 else 1)
            pixels, fill = paint_band(thickness)
            left = round(x * scale)
            # (where two lines cross, they're as opaque as the stronger of them, not more: as in a browser)
            line = Image.new("RGBA", (max(1, round(pixels)), size[1]), fill)
            under = layer.crop((left, 0, left + line.width, size[1]))
            layer.paste(_stronger(under, line), (left, 0))
    if pattern.kind == "dots":
        diameter = pattern.size
        pixels, fill = paint_band(diameter)
        for row in range(math.ceil((HEIGHT - pattern.offset) / spacing) + 1):
            y = pattern.offset + spacing / 2 + row * spacing
            for column in range(math.ceil(WIDTH / spacing) + 1):
                x = pattern.offset + spacing / 2 + column * spacing
                draw.ellipse(
                    (
                        (x - diameter / 2) * scale,
                        (y - diameter / 2) * scale,
                        (x - diameter / 2) * scale + pixels,
                        (y - diameter / 2) * scale + pixels,
                    ),
                    fill=fill,
                )
    return layer


def _stronger(under: Image.Image, over: Image.Image) -> Image.Image:
    """Of two layers of one colour, the more opaque one, pixel by pixel."""
    stronger = over.copy()
    stronger.putalpha(ImageChops.lighter(under.getchannel("A"), over.getchannel("A")))
    return stronger


@cache
def picture(background: SlideBackground, width: int = WIDTH) -> bytes:
    """The background as a PNG, width pixels wide (for a PowerPoint slide's background)."""
    scale = width / WIDTH
    canvas = Image.new("RGBA", (width, round(HEIGHT * scale)), background.color)
    paint(canvas, background.color, background.color_2, background.pattern, scale)
    output = io.BytesIO()
    canvas.convert("RGB").save(output, "PNG", optimize=True)
    return output.getvalue()


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
