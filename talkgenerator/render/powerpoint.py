"""Draw a deck as a PowerPoint presentation, in the classic look of the 2019 template.

The classic slide creators (`talkgenerator.slide.powerpoint_slide_creator`) still do the drawing: the renderer turns
each deck slide back into their arguments (see `talkgenerator.models.classic`), so a deck renders exactly like the
slides it was made from. Charts are rebuilt from their numbers and styled by their type (`talkgenerator.render.charts`),
and diagrams are drawn as shapes (`talkgenerator.render.diagrams`). The slide types that the template has no layout
for (milestone 6's: big numbers, quizzes, posts...) are laid out as in a themed deck, in the template's colours and
fonts, and drawn as shapes on its blank slide.

Images come from `images` when given (the images checked while generating, with their downloaded bytes and what to do
once they end up on a slide), and are downloaded otherwise. An image with a video plays it in its place, by itself and
looping (`talkgenerator.render.animation`), with the image as its poster frame.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from pptx.presentation import Presentation
from pptx.slide import Slide

from talkgenerator.datastructures.image_data import ImageData, VideoCopy
from talkgenerator.models import classic
from talkgenerator.models.deck import (
    ChartElement,
    Deck,
    DeckSlide,
    DiagramElement,
    ImageAsset,
    ImageElement,
    TextElement,
)
from talkgenerator.render import animation, charts
from talkgenerator.slide import powerpoint_slide_creator as creator
from talkgenerator.util import http_util, image_util, random_util

logger = logging.getLogger("talkgenerator")

ImageStore = Mapping[str, ImageData]

_CREATORS: dict[str, Callable[..., Slide | None]] = {
    "title": creator.create_title_slide,
    "large_quote": creator.create_large_quote_slide,
    "image": creator.create_image_slide,
    "full_image": creator.create_full_image_slide,
    "two_column_image": creator.create_two_column_images_slide,
    "three_column_image": creator.create_three_column_images_slide,
}
# The creators that take original_image_size: whether images are shown whole (padded) or fill their frame
_FITTING_CREATORS = frozenset({"image", "full_image", "two_column_image", "three_column_image"})


def render_pptx(
    deck: Deck,
    presentation: Presentation | None = None,
    *,
    debug_notes: bool = False,
    images: ImageStore | None = None,
) -> Presentation:
    """Add the deck's slides to the presentation (a new one if none is given): a classic deck's in the 2019
    template, a themed deck's as shapes (see talkgenerator.render.shapes), laid out first if it isn't yet."""
    if deck.theme != "classic":
        from talkgenerator.design import engine
        from talkgenerator.render.shapes import render_themed

        if deck.style is None:
            raise ValueError(f"A deck with theme {deck.theme!r} needs the theme's tokens (its style)")
        if not all(slide.layout.startswith("v5/") for slide in deck.slides):
            deck = engine.lay_out(deck, deck.style)
        return render_themed(deck, presentation, debug_notes=debug_notes, images=images)
    if presentation is None:
        presentation = creator.create_new_powerpoint()
    for slide in deck.slides:
        render_slide(presentation, slide, debug_notes=debug_notes, images=images)
    return presentation


def render_slide(
    presentation: Presentation,
    slide: DeckSlide,
    *,
    debug_notes: bool = False,
    images: ImageStore | None = None,
) -> Slide | None:
    """Add one deck slide to the presentation. With debug_notes, its speaker notes say how it was made."""
    if slide.layout != classic.layout_id(slide.type):
        raise ValueError(f"Can't draw layout {slide.layout!r}: only the classic layouts exist so far")
    if slide.type == "chart":
        ppt_slide: Slide | None = _create_chart_slide(presentation, slide)
    elif slide.type == "diagram":
        ppt_slide = _create_diagram_slide(presentation, slide)
    elif slide.type in classic.DRAWN_TYPES:
        ppt_slide = _create_drawn_slide(presentation, slide, images)
    elif slide.type in _CREATORS:
        ppt_slide = _CREATORS[slide.type](presentation, **_creator_arguments(slide, images))
    else:
        raise ValueError(f"Unknown slide type {slide.type!r}")
    if ppt_slide is not None:
        _finish(ppt_slide, slide, debug_notes)
    return ppt_slide


def _creator_arguments(slide: DeckSlide, images: ImageStore | None) -> dict[str, Any]:
    roles = classic.CLASSIC_ROLES[slide.type]
    argument_of_role = {role: argument for argument, role in roles.items()}
    arguments: dict[str, Any] = dict.fromkeys(roles)
    fits = []
    for element in slide.elements:
        argument = argument_of_role.get(element.role)
        if argument is None:
            raise ValueError(f"A {slide.type} slide has no place for {element.role!r}")
        if isinstance(element, TextElement):
            arguments[argument] = element.text
        elif isinstance(element, ImageElement):
            arguments[argument] = image_data(element.image, images)
            if element.role not in classic.COVER_ROLES:
                fits.append(element.fit)
        else:
            raise ValueError(f"A {slide.type} slide can't hold a {element.kind}")
    if slide.type in _FITTING_CREATORS:
        arguments["original_image_size"] = all(fit == "contain" for fit in fits)
    return arguments


def _create_chart_slide(presentation: Presentation, slide: DeckSlide) -> Slide:
    chart_element = slide.element("chart")
    if not isinstance(chart_element, ChartElement):
        raise ValueError("A chart slide needs its chart")
    title = slide.element("title")
    spec = chart_element.chart
    chart_type, chart_data = charts.pptx_chart_data(spec)
    ppt_slide: Slide = creator.create_chart_slide(
        presentation,
        title.text if isinstance(title, TextElement) else None,
        chart_type,
        chart_data,
        charts.CHART_STYLES[spec.chart_type],
    )
    frame: Any = next(shape for shape in ppt_slide.shapes if getattr(shape, "has_chart", False))
    charts.set_axis_titles(frame.chart, spec)
    charts.label_points(frame.chart, spec, charts.CLASSIC_LOOK, frame.width)
    charts.finish(frame.chart, charts.CLASSIC_LOOK)
    if spec.reveal == "series":
        animation.reveal_chart_series(ppt_slide, frame, len(spec.series))
    return ppt_slide


def _create_diagram_slide(presentation: Presentation, slide: DeckSlide) -> Slide:
    diagram_element = slide.element("diagram")
    if not isinstance(diagram_element, DiagramElement):
        raise ValueError("A diagram slide needs its diagram")
    title = slide.element("title")
    ppt_slide: Slide = creator.create_diagram_slide(
        presentation, title.text if isinstance(title, TextElement) else None, diagram_element.diagram
    )
    return ppt_slide


def _create_drawn_slide(presentation: Presentation, slide: DeckSlide, images: ImageStore | None) -> Slide:
    """A slide of a type that the 2019 template has no layout for (a big number, a quiz...): laid out in the
    template's look and drawn as shapes on its blank slide, as a themed deck draws it, with its credits where the
    template has them (see _finish). Every slide of a type and its elements gets the same layout."""
    from talkgenerator.design import engine, themes  # (they draw on this module)
    from talkgenerator.render import shapes

    look = themes.CLASSIC_LOOK
    ppt_slide: Slide = presentation.slides.add_slide(presentation.slide_layouts[creator.LAYOUT_BLANK])
    placed = engine.lay_out_slide(slide, look, random_util.Rng(0).child("classic", slide.type))
    # (without the band that the credits of a themed deck's full-screen photo go on: the template has its own place)
    elements = tuple(element for element in placed.elements if element.role != "credits band")
    shapes.draw_elements(ppt_slide, placed.model_copy(update={"elements": elements}), look, images=images)
    return ppt_slide


def image_data(image: ImageAsset, images: ImageStore | None) -> ImageData:
    """The image of a deck's image: the one generating found, if the store has it, else one that downloads it (and
    its video, if it plays one). Themed decks' pictures come from here too (talkgenerator.render.shapes)."""
    known = images.get(image.url) if images is not None else None
    if known is not None:
        return known
    credit = [(part.text, part.url) for part in image.credit]
    found = ImageData(image_url=image.url, source=image.source, source_url=image.source_url, credit=credit or None)
    if image.video_url:
        found.video = VideoCopy(url=image.video_url, poster_url=image.url)
        found.video_data = image_util.fetch_video(image.video_url)
        found.plays_video = found.video_data is not None
        if found.video_data is None:
            video = http_util.describe_url(image.video_url)
            logger.warning("Showing video %s as its poster frame: it can't be downloaded or used", video)
    return found


def _finish(ppt_slide: Slide, slide: DeckSlide, debug_notes: bool) -> None:
    try:
        if debug_notes and slide.notes:
            notes = ppt_slide.notes_slide.notes_text_frame
            if notes is not None:
                notes.text = slide.notes
        if slide.credits:
            creator.add_sources_note(
                ppt_slide, [[(part.text, part.url) for part in credit] for credit in slide.credits]
            )
        creator.remove_empty_placeholders(ppt_slide)
        creator.animate_like_layout(ppt_slide)  # (after: only the shapes the slide keeps are animated)
    except (AttributeError, KeyError) as e:
        logger.error("Error while finishing slide: {}".format(e))
