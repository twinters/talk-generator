"""Pictures of a themed deck's slides, drawn with Pillow from their positioned elements (docs/v5-plan.md, 9 and 14).

A preview uses the boxes, fonts, sizes and line breaks that the layout engine picked, so it shows where texts break
and whether they fit; charts are sketched (their kind, colours and labels), and diagrams are drawn from the same
geometry and labels as in PowerPoint (`talkgenerator.render.diagrams`). A contact sheet shows a whole deck at a
glance. A preview shows everything on a slide, as an editor does, or a step of it as it's presented: what shows
after so many clicks (`talkgenerator.render.reveal`; a chart and a diagram whole); a sheet of steps shows them side
by side. Classic decks have no positions (the 2019 template places their elements), so they have no previews.
"""

from __future__ import annotations

import io
import logging
import math
from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, fit, fonts, geometry, treatments
from talkgenerator.design.engine import HEIGHT, WIDTH
from talkgenerator.models.deck import (
    Box,
    ChartElement,
    Content,
    Deck,
    DeckSlide,
    DiagramElement,
    ImageElement,
    ImageTreatment,
    ShapeElement,
    TextElement,
    TextStyle,
    VennDiagram,
)
from talkgenerator.models.theme import TextEffect, Theme
from talkgenerator.render import backgrounds, diagrams, reveal
from talkgenerator.util import emoji_util, image_util

logger = logging.getLogger("talkgenerator")

ImageStore = Mapping[str, ImageData]
_Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def slide_image(
    slide: DeckSlide, theme: Theme, images: ImageStore | None = None, width: int = 960, step: int | None = None
) -> Image.Image:
    """A picture of the slide, width pixels wide: with everything on it, or (with a step) as it shows after that
    many clicks (0: as it comes up), with what hasn't appeared yet left out and a column that has had its turn
    dimmed."""
    scale = width / WIDTH
    canvas = Image.new("RGBA", (width, round(HEIGHT * scale)), theme.palette.background)
    if slide.background is not None:
        background = slide.background
        backgrounds.paint(canvas, background.color, background.color_2, background.pattern, scale)
    for element in slide.elements:
        shown = 1.0 if step is None else reveal.opacity(slide, element, step)
        if shown <= 0:
            continue
        layer = canvas if shown >= 1 else Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        _element(layer, element, scale, images, slide.style or theme)
        if layer is not canvas:  # (dimmed)
            layer.putalpha(layer.getchannel("A").point([round(value * shown) for value in range(256)]))
            canvas.alpha_composite(layer)
    if slide.credits and slide.credits_box is not None and slide.credits_style is not None:
        line = engine.credit_line(slide.credits, engine.credits_prefix(slide))
        _text(canvas, line, slide.credits_box, slide.credits_style, scale)
    return canvas.convert("RGB")


def _element(canvas: Image.Image, element: Content, scale: float, images: ImageStore | None, theme: Theme) -> None:
    if isinstance(element, ShapeElement):
        _shape(canvas, element, scale)
    elif isinstance(element, ImageElement) and element.box is not None:
        _image(canvas, element, scale, images)
    elif isinstance(element, ChartElement) and element.box is not None:
        _chart(canvas, element, scale, theme)
    elif isinstance(element, DiagramElement) and element.box is not None and element.style is not None:
        _diagram(canvas, element, scale)
    elif isinstance(element, TextElement) and element.box is not None and element.style is not None:
        _text(canvas, element.text, element.box, element.style, scale)


def contact_sheet(deck: Deck, images: ImageStore | None = None, columns: int = 3, width: int = 480) -> Image.Image:
    """Every slide of the deck, in a grid, numbered."""
    if deck.style is None:
        raise ValueError("A classic deck has no previews: the 2019 template places its elements")
    pictures = [slide_image(slide, slide.style or deck.style, images, width) for slide in deck.slides]
    gutter, label = 16, 28
    rows = max(1, math.ceil(len(pictures) / columns))
    height = round(HEIGHT * width / WIDTH)
    sheet = Image.new(
        "RGB", (columns * (width + gutter) + gutter, rows * (height + label + gutter) + gutter), "#f2f2f2"
    )
    draw = ImageDraw.Draw(sheet)
    for index, picture in enumerate(pictures):
        x = gutter + (index % columns) * (width + gutter)
        y = gutter + (index // columns) * (height + label + gutter)
        draw.text((x, y), f"{index + 1}. {deck.slides[index].layout}", fill="#333333", font=_font("Arial", 16))
        sheet.paste(picture, (x, y + label))
    return sheet


def steps_sheet(deck: Deck, images: ImageStore | None = None, width: int = 320) -> Image.Image:
    """The slides that take clicks, a row each: the slide as it comes up, then after each of its clicks (numbered
    by the slide's place in the deck, and its step)."""
    if deck.style is None:
        raise ValueError("A classic deck has no previews: the 2019 template places its elements")
    rows = [(number, slide) for number, slide in enumerate(deck.slides, 1) if reveal.clicks(slide)]
    gutter, label = 16, 28
    height = round(HEIGHT * width / WIDTH)
    most = max((reveal.clicks(slide) + 1 for _, slide in rows), default=1)
    sheet = Image.new(
        "RGB", (most * (width + gutter) + gutter, max(1, len(rows)) * (height + label + gutter) + gutter), "#f2f2f2"
    )
    draw = ImageDraw.Draw(sheet)
    for row, (number, slide) in enumerate(rows):
        y = gutter + row * (height + label + gutter)
        for step in range(reveal.clicks(slide) + 1):
            x = gutter + step * (width + gutter)
            caption = f"{number}. {slide.layout}" if step == 0 else f"click {step}"
            draw.text((x, y), caption, fill="#333333", font=_font("Arial", 16))
            sheet.paste(slide_image(slide, slide.style or deck.style, images, width, step), (x, y + label))
    return sheet


def save_previews(deck: Deck, folder: Path, images: ImageStore | None = None, width: int = 960) -> list[Path]:
    """A PNG of every slide (slide-01.png, ...), and the contact sheet (slides.png), in the folder."""
    if deck.style is None:
        raise ValueError("A classic deck has no previews: the 2019 template places its elements")
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for number, slide in enumerate(deck.slides, 1):
        path = folder / f"slide-{number:02}.png"
        slide_image(slide, slide.style or deck.style, images, width).save(path)
        paths.append(path)
    sheet = folder / "slides.png"
    contact_sheet(deck, images).save(sheet)
    return [*paths, sheet]


# DRAWING


# Shapes are drawn this many times larger, then made smaller, so that their edges are smooth
_SUPERSAMPLE = 3


def _shape(canvas: Image.Image, shape: ShapeElement, scale: float) -> None:
    """The shape as PowerPoint draws it: filled (or not), with its outline inside its box, turned around its middle,
    and as see-through as it is (fill and outline alike). Drawn larger on a layer of its own, around it, and made
    smaller onto the slide, for smooth edges."""
    bounds = geometry.bounds(shape)
    pad = 2
    left, top = math.floor(bounds.x * scale) - pad, math.floor(bounds.y * scale) - pad
    right, bottom = math.ceil((bounds.x + bounds.w) * scale) + pad, math.ceil((bounds.y + bounds.h) * scale) + pad
    if right <= 0 or bottom <= 0 or left >= canvas.width or top >= canvas.height:
        return
    big = _SUPERSAMPLE * scale
    size = (max(1, (right - left) * _SUPERSAMPLE), max(1, (bottom - top) * _SUPERSAMPLE))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def at(point: tuple[float, float]) -> tuple[float, float]:
        return point[0] * big - left * _SUPERSAMPLE, point[1] * big - top * _SUPERSAMPLE

    fill = (*_rgb(shape.color), 255) if shape.filled else None
    line = (*_rgb(shape.outline), 255) if shape.outline and shape.outline_width > 0 else None
    width = max(1, round(shape.outline_width * big)) if line else 0
    box = shape.box
    rect = (*at((box.x, box.y)), *at((box.x + box.w, box.y + box.h)))
    if shape.rotation or shape.shape == "polygon":
        corners = [at(corner) for corner in geometry.outline(shape)]
        if fill is not None:
            draw.polygon(corners, fill=fill)
        if line is not None:  # (an outline inside its edge: the same, a line's width further in, cut out)
            ring = Image.new("L", size, 0)
            ImageDraw.Draw(ring).polygon(corners, fill=255)
            inner = ring.filter(ImageFilter.MinFilter(2 * (width // 2) + 1))
            layer.paste(Image.new("RGBA", size, line), (0, 0), ImageChops.subtract(ring, inner))
    elif shape.shape == "ellipse":
        draw.ellipse(rect, fill=fill, outline=line, width=width)
    elif shape.corner > 0:
        draw.rounded_rectangle(rect, radius=shape.corner * big, fill=fill, outline=line, width=width)
    else:
        draw.rectangle(rect, fill=fill, outline=line, width=width)
    layer = layer.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    if shape.opacity < 1:
        layer.putalpha(layer.getchannel("A").point(lambda value: round(value * shape.opacity)))
    _composite(canvas, layer, left, top)


def _composite(canvas: Image.Image, layer: Image.Image, left: int, top: int) -> None:
    """Lay the layer over the canvas with its top left corner at (left, top), which may be off the canvas."""
    crop_left, crop_top = max(0, -left), max(0, -top)
    if crop_left or crop_top:
        layer = layer.crop((crop_left, crop_top, layer.width, layer.height))
        left, top = left + crop_left, top + crop_top
    if layer.width <= 0 or layer.height <= 0 or left >= canvas.width or top >= canvas.height:
        return
    layer = layer.crop((0, 0, min(layer.width, canvas.width - left), min(layer.height, canvas.height - top)))
    canvas.alpha_composite(layer, (left, top))


def _image(canvas: Image.Image, element: ImageElement, scale: float, images: ImageStore | None) -> None:
    assert element.box is not None
    known = images.get(element.image.url) if images is not None else None
    data = image_util.fetch_image_data(known) if known is not None else image_util.fetch_image(element.image.url)
    if data is None:
        return
    try:
        with Image.open(io.BytesIO(data)) as opened:
            x0, y0, x1, y1 = _rect(element.box, scale)
            opened.draft("RGB", (max(1, x1 - x0), max(1, y1 - y0)))  # (a big JPEG decoded at about its shown size)
            picture = opened.convert("RGB")  # (a gif's first frame)
    except Exception:  # a picture Pillow can't read: the preview goes without
        logger.debug("Can't preview %s", element.image.url, exc_info=True)
        return
    look = element.treatment or ImageTreatment()
    box, frame = element.box, None
    if look.frame == "polaroid":
        frame, box = treatments.polaroid(element.box, picture.width, picture.height, element.fit == "cover")
    shown, (left, top) = _fitted(picture, box, element.fit, scale)
    shown = treatments.filtered(shown, look)
    if frame is not None:
        _polaroid(canvas, shown, (left, top), frame, look.tilt, scale)
        return
    canvas.paste(shown, (left, top), treatments.rounded_mask(shown.size) if look.frame == "rounded" else None)
    if element.border:
        placed = (left, top, left + shown.width, top + shown.height)
        draw, line = ImageDraw.Draw(canvas), max(1, round(6 * scale))
        if look.frame == "rounded":
            draw.rounded_rectangle(placed, treatments.ROUNDED * min(shown.size), outline=element.border, width=line)
        else:
            draw.rectangle(placed, outline=element.border, width=line)


def _fitted(picture: Image.Image, box: Box, fit: str, scale: float) -> tuple[Image.Image, tuple[int, int]]:
    """The picture as it's shown in the box (filling it, cropped, or whole), and where it goes on the canvas."""
    x0, y0, x1, y1 = _rect(box, scale)
    width, height = max(1, x1 - x0), max(1, y1 - y0)
    if fit == "cover":
        ratio = max(width / picture.width, height / picture.height)
        resized = picture.resize((max(1, round(picture.width * ratio)), max(1, round(picture.height * ratio))))
        left, top = (resized.width - width) // 2, (resized.height - height) // 2
        return resized.crop((left, top, left + width, top + height)), (x0, y0)
    ratio = min(width / picture.width, height / picture.height)
    resized = picture.resize((max(1, round(picture.width * ratio)), max(1, round(picture.height * ratio))))
    return resized, (x0 + (width - resized.width) // 2, y0 + (height - resized.height) // 2)


def _polaroid(
    canvas: Image.Image, shown: Image.Image, at: tuple[int, int], frame: Box, tilt: float, scale: float
) -> None:
    """The picture on its white polaroid frame, the two turned as one around the frame's middle."""
    x0, y0, x1, y1 = _rect(frame, scale)
    card = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), treatments.POLAROID_WHITE)
    card.paste(shown, (at[0] - x0, at[1] - y0))
    turned = card.rotate(-tilt, resample=Image.Resampling.BICUBIC, expand=True)  # (Pillow turns anticlockwise)
    middle_x, middle_y = (x0 + x1) / 2, (y0 + y1) / 2
    canvas.paste(turned, (round(middle_x - turned.width / 2), round(middle_y - turned.height / 2)), turned)


def _text(canvas: Image.Image, text: str, box: Box, style: TextStyle, scale: float) -> None:
    shown = text.upper() if style.uppercase else text
    lines = fit.wrap(shown, box.w, style.font, style.size, style.bold)
    font = _font(style.font, style.size * scale, style.bold)
    draw = ImageDraw.Draw(canvas)
    line_height = style.size * fit.LINE_HEIGHT * scale
    total = line_height * len(lines)
    x0, y0, x1, y1 = (value * scale for value in (box.x, box.y, box.x + box.w, box.y + box.h))
    top = {"top": y0, "middle": y0 + (y1 - y0 - total) / 2, "bottom": y1 - total}[style.anchor]
    placed = []
    for index, line in enumerate(lines):
        length = _line_length(draw, line, font, style.size * scale)
        left = {"left": x0, "center": x0 + (x1 - x0 - length) / 2, "right": x1 - length}[style.align]
        placed.append((left, top + index * line_height + (line_height - style.size * scale) / 2, line))
    if style.effect is None:
        for left, y, line in placed:
            _draw_line(draw, (left, y), line, style.color, font, style.size * scale)
        return
    _with_effect(canvas, placed, font, style.color, style.effect, scale, (x0, y0, x1, y1))


def _line_length(draw: ImageDraw.ImageDraw, line: str, font: _Font, size: float) -> float:
    """How long a line is drawn: its emoji as wide as they're measured (talkgenerator.util.emoji_util)."""
    return sum(
        emoji_util.count(part) * emoji_util.WIDTH * size if emoji else draw.textlength(part, font=font)
        for part, emoji in emoji_util.runs(line)
    )


def _draw_line(
    draw: ImageDraw.ImageDraw, at: tuple[float, float], line: str, colour: str, font: _Font, size: float
) -> None:
    """A line of text, its emoji in colour in an emoji font (each by itself, where this computer has one), as
    PowerPoint and browsers draw them."""
    x, y = at
    for part, emoji in emoji_util.runs(line):
        if not emoji:
            draw.text((x, y), part, fill=colour, font=font)
            x += draw.textlength(part, font=font)
            continue
        emoji_font = _emoji_font(size)
        for index, character in enumerate(part):
            selected = index + 1 < len(part) and part[index + 1] == "️"
            if emoji_util.count(character) or selected:
                if emoji_font is not None:
                    draw.text((x, y), character, font=emoji_font, embedded_color=True)
                x += emoji_util.WIDTH * size


def _emoji_font(size: float) -> ImageFont.FreeTypeFont | None:
    path = fonts.emoji_font_file()
    return ImageFont.truetype(str(path), max(1, round(size))) if path is not None else None


def _with_effect(
    canvas: Image.Image,
    placed: list[tuple[float, float, str]],
    font: _Font,
    colour: str,
    effect: TextEffect,
    scale: float,
    area: tuple[float, float, float, float],
) -> None:
    """A text's lines with WordArt-style effects, as PowerPoint draws them: its glow and shadow behind it, its
    outline, its fill (a gradient from the top of the text down, or its colour), all bent into the warp's shape."""
    mask = Image.new("L", canvas.size, 0)
    pen = ImageDraw.Draw(mask)
    for left, y, line in placed:
        pen.text((left, y), line, fill=255, font=font)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    if effect.glow and effect.glow_radius > 0:
        radius = max(1, round(effect.glow_radius * scale))
        glow = mask.filter(ImageFilter.MaxFilter(2 * (radius // 2) + 1)).filter(ImageFilter.GaussianBlur(radius / 2))
        _paint(layer, glow, effect.glow, 0.6)
    if effect.shadow:
        right, down = (round(value * scale) for value in effect.shadow_offset)
        shadow = Image.new("L", canvas.size, 0)
        shadow.paste(mask, (right, down))
        if effect.shadow_blur > 0:
            shadow = shadow.filter(ImageFilter.GaussianBlur(effect.shadow_blur * scale))
        _paint(layer, shadow, effect.shadow, effect.shadow_opacity)
    if effect.outline and effect.outline_width > 0:
        stroke = Image.new("L", canvas.size, 0)
        width = max(1, round(effect.outline_width * scale))
        outline_pen = ImageDraw.Draw(stroke)
        for left, y, line in placed:
            outline_pen.text((left, y), line, fill=255, font=font, stroke_width=width, stroke_fill=255)
        _paint(layer, stroke, effect.outline, 1.0)
    if effect.fill:
        top = placed[0][1]
        bottom = placed[-1][1] + font.size if isinstance(font, ImageFont.FreeTypeFont) else placed[-1][1] + 10
        layer.paste(_gradient(canvas.size, effect.fill, top, bottom), (0, 0), mask)
    else:
        _paint(layer, mask, colour, 1.0)
    if effect.warp:
        layer = _warped(layer, area, effect.warp)
    canvas.alpha_composite(layer)


def _paint(layer: Image.Image, mask: Image.Image, colour: str, opacity: float) -> None:
    tinted = Image.new("RGBA", layer.size, (*_rgb(colour), 0))
    tinted.putalpha(mask.point(lambda value: round(value * opacity)))
    layer.alpha_composite(tinted)


def _gradient(size: tuple[int, int], stops: tuple[str, ...], top: float, bottom: float) -> Image.Image:
    """An image of the colours, from the first at the top to the last at the bottom (and beyond)."""
    colours = [_rgb(stop) for stop in stops]
    height = max(2, round(bottom - top))
    column = Image.new("RGB", (1, height))
    for y in range(height):
        position = y / (height - 1) * (len(colours) - 1)
        low = min(int(position), len(colours) - 2) if len(colours) > 1 else 0
        share = position - low if len(colours) > 1 else 0.0
        first, second = colours[low], colours[min(low + 1, len(colours) - 1)]
        column.putpixel((0, y), tuple(round(a + (b - a) * share) for a, b in zip(first, second, strict=True)))
    image = Image.new("RGBA", size, (*colours[-1], 255))
    image.paste(Image.new("RGBA", (size[0], max(0, round(top))), (*colours[0], 255)), (0, 0))
    image.paste(column.resize((size[0], height)), (0, round(top)))
    return image


def _warped(layer: Image.Image, area: tuple[float, float, float, float], warp: str) -> Image.Image:
    """The layer with what's in the area (and a little around it, for shadows) bent into one of WordArt's shapes, and
    squeezed first so that it stays in its box, as PowerPoint keeps it: strips of it moved up and down (or stretched,
    to inflate it)."""
    margin = 0.08 * (area[2] - area[0])
    x0, y0 = max(0, round(area[0] - margin)), max(0, round(area[1] - margin))
    x1, y1 = min(layer.width, round(area[2] + margin)), min(layer.height, round(area[3] + margin))
    region = layer.crop((x0, y0, x1, y1))
    width, height = region.size
    amplitude = 0.12 * (area[3] - area[1])
    stretch = 1.3  # (how much taller an inflated middle is)
    room = height / stretch if warp == "inflate" else height - 2 * amplitude
    squeezed = region.resize((width, max(1, round(room))))
    bent = Image.new("RGBA", region.size, (0, 0, 0, 0))
    for x in range(0, width, 2):
        strip = squeezed.crop((x, 0, min(width, x + 2), squeezed.height))
        share = (x + 1) / max(1, width)
        if warp == "inflate":  # taller in the middle
            tall = strip.resize(
                (strip.width, max(1, round(squeezed.height * (1 + (stretch - 1) * (1 - (2 * share - 1) ** 2)))))
            )
            bent.paste(tall, (x, round((height - tall.height) / 2)), tall)
            continue
        if warp == "wave":
            lift = amplitude * math.sin(2 * math.pi * share)
        elif warp == "arch":
            lift = -amplitude * (1 - (2 * share - 1) ** 2)
        else:  # slant: rising to the right
            lift = amplitude * (1 - 2 * share)
        bent.paste(strip, (x, round(amplitude + lift)), strip)
    result = layer.copy()
    result.paste((0, 0, 0, 0), (x0, y0, x1, y1))
    result.alpha_composite(bent, (x0, y0))
    return result


def _chart(canvas: Image.Image, element: ChartElement, scale: float, theme: Theme) -> None:
    """A sketch of the chart: its bars, lines, slices or points in the theme's colours, and its labels."""
    assert element.box is not None
    spec, palette = element.chart, theme.palette
    draw = ImageDraw.Draw(canvas)
    colors = [palette.accent, palette.accent_2, palette.muted, palette.text]
    x0, y0, x1, y1 = _rect(element.box, scale)
    label = _font(theme.fonts.body, 28 * scale)
    if spec.chart_type in ("pie", "doughnut"):
        doughnut = spec.chart_type == "doughnut"
        size = min(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        values = spec.series[0].values if spec.series else ()
        total = sum(values) or 1
        start = -90.0
        for index, value in enumerate(values):
            end = start + 360 * value / total
            draw.pieslice(
                (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2), start, end, fill=colors[index % 4]
            )
            middle = math.radians((start + end) / 2)
            name = spec.categories[index] if index < len(spec.categories) else ""
            reach = 0.375 if doughnut else 0.3  # (a doughnut's share on its ring, its name in the legend)
            draw.text(
                (cx + math.cos(middle) * size * reach, cy + math.sin(middle) * size * reach),
                f"{value / total:.0%}" if doughnut else name,
                fill=palette.text,
                font=label,
                anchor="mm",
            )
            if doughnut:
                key = cy + (index - len(values) / 2) * 36 * scale
                draw.rectangle(
                    (cx + size * 0.6, key - 8 * scale, cx + size * 0.6 + 16 * scale, key + 8 * scale),
                    fill=colors[index % 4],
                )
                draw.text((cx + size * 0.6 + 26 * scale, key), name, fill=palette.text, font=label, anchor="lm")
            start = end
        if doughnut:
            draw.ellipse((cx - size / 4, cy - size / 4, cx + size / 4, cy + size / 4), fill=palette.background)
        return
    left, bottom = x0 + 60 * scale, y1 - 60 * scale
    axes = {"column": [(left, bottom), (x1, bottom)], "bar": [(left, y0), (left, bottom)]}  # (only what's drawn)
    axis = axes.get(spec.chart_type, [(left, y0), (left, bottom), (x1, bottom)])
    draw.line(axis, fill=palette.muted, width=max(1, round(3 * scale)))
    if spec.x_title:
        draw.text(((left + x1) / 2, y1 - 20 * scale), spec.x_title, fill=palette.text, font=label, anchor="mm")
    if spec.y_title:
        draw.text((x0 + 20 * scale, (y0 + bottom) / 2), spec.y_title[:24], fill=palette.text, font=label, anchor="lm")
    if spec.chart_type == "scatter":
        points = [point for series in spec.series for point in series.points]
        if not points:
            return
        top_x = max(x for x, _ in points) or 1
        top_y = max(y for _, y in points) or 1
        for number, series in enumerate(spec.series):
            for index, (px, py) in enumerate(series.points):
                x = left + (x1 - left) * px / top_x * 0.95
                y = bottom - (bottom - y0) * py / top_y * 0.95
                radius = (12 if index < len(series.labels) and series.labels[index] else 5) * scale
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colors[number % 4])
        return
    every_value = [value for series in spec.series for value in series.values]
    top_value = max(every_value, default=1) or 1
    if spec.chart_type == "line":
        for number, series in enumerate(spec.series):
            count = max(1, len(series.values) - 1)
            line = [
                (left + (x1 - left) * index / count, bottom - (bottom - y0) * value / top_value * 0.9)
                for index, value in enumerate(series.values)
            ]
            if len(line) > 1:
                draw.line(line, fill=colors[number % 4], width=max(1, round(10 * scale)))
            for index, name in enumerate(series.labels):
                if name and index < len(line):
                    x, y = line[index]
                    draw.ellipse(
                        (x - 14 * scale, y - 14 * scale, x + 14 * scale, y + 14 * scale), fill=palette.accent_2
                    )
                    draw.text((x, y - 30 * scale), name, fill=palette.text, font=label, anchor="mb")
        return
    series_values = spec.series[0].values if spec.series else ()
    count = max(1, len(series_values))
    for index, value in enumerate(series_values):
        fill = palette.accent_2 if spec.chart_type == "bar" and index == count - 1 else palette.accent
        if spec.chart_type == "bar":  # horizontal, the first category at the bottom
            height = (bottom - y0) / count
            top = bottom - (index + 1) * height
            draw.rectangle(
                (left, top + height * 0.15, left + (x1 - left) * value / top_value * 0.9, top + height * 0.85),
                fill=fill,
            )
            name = spec.categories[index] if index < len(spec.categories) else ""
            draw.text((left + 10 * scale, top + height / 2), name, fill=palette.background, font=label, anchor="lm")
        else:  # a column, with its share on top
            span = (x1 - left) / count
            top = bottom - (bottom - y0) * value / top_value * 0.85
            draw.rectangle(
                (left + index * span + span * 0.15, top, left + (index + 1) * span - span * 0.15, bottom), fill=fill
            )
            draw.text(
                (left + (index + 0.5) * span, top - 6 * scale),
                f"{value:.0%}",
                fill=palette.text,
                font=label,
                anchor="mb",
            )


def _diagram(canvas: Image.Image, element: DiagramElement, scale: float) -> None:
    """The diagram as the renderer draws it: its see-through circles or quadrants, its axes and dot, and its labels."""
    assert element.box is not None and element.style is not None
    style, diagram = element.style, element.diagram
    frame = diagrams.Box.on_canvas(element.box)

    def at(value: float) -> float:  # a place on the slide (in EMU), in the picture
        return value / diagrams.EMU_PER_PIXEL * scale

    see_through = round(255 * style.opacity)
    line = max(1, round(4 * scale))  # (2 points)
    if isinstance(diagram, VennDiagram):
        layout = diagrams.venn_layout_for(frame, diagram, style.font)  # (its labels in its circles, or beside them)
        radius = layout.radius
        for (x, y), fill in zip(layout.centres, style.fills, strict=False):
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))  # (a layer each, so that where they overlap, they mix)
            ImageDraw.Draw(layer).ellipse(
                (at(x - radius), at(y - radius), at(x + radius), at(y + radius)),
                fill=(*_rgb(fill), see_through),
                outline=fill,
                width=line,
            )
            canvas.alpha_composite(layer)
    else:
        matrix = diagrams.matrix_layout(frame)
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        tints = ImageDraw.Draw(layer)
        for quadrant, fill in zip(matrix.quadrants, style.fills, strict=False):
            tints.rectangle(
                (at(quadrant.left), at(quadrant.top), at(quadrant.right), at(quadrant.bottom)),
                fill=(*_rgb(fill), see_through),
            )
        canvas.alpha_composite(layer)
        draw = ImageDraw.Draw(canvas)
        for _, (x0, y0), (x1, y1) in matrix.axes():
            draw.line([(at(x0), at(y0)), (at(x1), at(y1))], fill=style.lines, width=max(1, round(5 * scale)))
        dot = matrix.dot(diagram.dot_x, diagram.dot_y)
        draw.ellipse(
            (at(dot.left), at(dot.top), at(dot.right), at(dot.bottom)),
            fill=style.punchline,
            outline=style.outline,
            width=line,
        )
    for label in diagrams.labels(frame, diagram, style.font):
        look = TextStyle(
            font=style.font,
            size=2 * label.size,  # (a canvas pixel is half a point)
            color=style.punchline if label.colour == "punchline" else style.text,
            bold=label.bold,
            italic=label.italic,
            align=label.align,
            anchor=label.anchor,
        )
        _text(canvas, label.text, diagrams.text_area(label.box), look, scale)


def _font(name: str, size: float, bold: bool = False) -> _Font:
    path = fonts.font_file(name, bold)
    pixels = max(1, round(size))
    if path is None:
        return ImageFont.load_default(pixels)
    return ImageFont.truetype(str(path), pixels)


def _rect(box: Box, scale: float) -> tuple[int, int, int, int]:
    return (round(box.x * scale), round(box.y * scale), round((box.x + box.w) * scale), round((box.y + box.h) * scale))


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
