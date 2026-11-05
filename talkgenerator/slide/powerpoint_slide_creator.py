import logging
from collections.abc import Sequence
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pptx
from lxml.etree import XMLSyntaxError
from pptx.presentation import Presentation

from talkgenerator.datastructures.image_data import CreditPart, ImageData
from talkgenerator.util import http_util, image_util, os_util

# Location of powerpoint template
_POWERPOINT_TEMPLATE_FILE = "data/powerpoint/template.pptx"

logger = logging.getLogger("talkgenerator")


@lru_cache(maxsize=1)
def get_powerpoint_template_file():
    return os_util.to_actual_file(_POWERPOINT_TEMPLATE_FILE)


SOURCES_PLACEHOLDER = 10

# Layouts index in template
LAYOUT_TITLE_SLIDE = 0
LAYOUT_TITLE_AND_CONTENT = 1
LAYOUT_SECTION_HEADER = 2
LAYOUT_TWO_CONTENT = 3
LAYOUT_TWO_TITLE_AND_CONTENT = 4
LAYOUT_TITLE_ONLY = 5
LAYOUT_BLANK = 6
LAYOUT_CONTENT_CAPTION = 7
LAYOUT_PICTURE_CAPTION = 8
LAYOUT_FULL_PICTURE = 11
LAYOUT_TITLE_AND_PICTURE = 12
LAYOUT_LARGE_QUOTE = 13
LAYOUT_TWO_TITLE_AND_IMAGE = 14
LAYOUT_THREE_TITLE_AND_IMAGE = 15
LAYOUT_TITLE_AND_CHART = 16


# CREATION
def _create_slide(prs, slide_type):
    """Creates a new slide in the given presentation using the slide_type template"""
    return prs.slides.add_slide(prs.slide_layouts[slide_type])


def _add_title(slide, title):
    """Adds the given title to the slide if the title is present"""
    if title:
        title_object = slide.shapes.title
        title_object.text = title
        return True


def _add_text(slide, placeholder_id, text):
    if text:
        placeholder = slide.placeholders[placeholder_id]
        placeholder.text = str(text)
        return True


def is_external_url(url: str):
    return url.startswith("http")


def _remove_shape(shape):
    """Remove an unfilled placeholder, so the deck doesn't show an empty "click to add picture" frame."""
    element = shape._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def remove_empty_placeholders(slide):
    """Drop placeholders that never got content (e.g. no title, or no image sources), so they don't
    show up as "Click to add text" boxes when the deck is edited."""
    for placeholder in list(slide.placeholders):
        if placeholder.has_text_frame and not placeholder.text_frame.text.strip():
            _remove_shape(placeholder)


def _add_image(slide, placeholder_id: int, image: ImageData, original_image_size: bool = True):
    image_url = image.get_image_url() if isinstance(image, ImageData) else image
    if not is_external_url(image_url):
        image_url = str(Path(image_url).absolute())

    placeholder = slide.placeholders[placeholder_id]
    # An ImageData that was checked while generating already holds its bytes
    image_bytes = image_util.fetch_image_data(image) if isinstance(image, ImageData) else None
    if image_bytes is None:
        image_bytes = image_util.fetch_image(image_url)
    if image_bytes is None:
        logger.warning("Leaving out image %s: it could not be downloaded or used", http_util.describe_url(image_url))
        _remove_shape(placeholder)
        return None

    try:
        if original_image_size:
            width, height = image_util.get_image_size(image_bytes)
            # Make the placeholder match the image, so that python-pptx doesn't crop (zoom in on) it
            placeholder.height = height
            placeholder.width = width
            picture = placeholder.insert_picture(BytesIO(image_bytes))
            # Then pad the picture so it fits inside the layout's frame with its own aspect ratio
            image_ratio = width / height
            placeholder_ratio = picture.width / picture.height
            ratio_difference = placeholder_ratio - image_ratio
            # Placeholder width too wide:
            if ratio_difference > 0:
                difference_on_each_side = ratio_difference / 2
                picture.crop_left = -difference_on_each_side
                picture.crop_right = -difference_on_each_side
            # Placeholder height too high
            else:
                difference_on_each_side = -ratio_difference / 2
                picture.crop_bottom = -difference_on_each_side
                picture.crop_top = -difference_on_each_side
        else:
            picture = placeholder.insert_picture(BytesIO(image_bytes))
    except (ValueError, XMLSyntaxError, AttributeError, OSError, KeyError) as e:
        logger.error("Could not insert image %s: %s", http_util.describe_url(image_url), e)
        if placeholder._element.getparent() is not None:
            _remove_shape(placeholder)
        return None

    if isinstance(image, ImageData):
        image.mark_used()
    return picture


def _add_chart(slide, placeholder_id, chart_type, chart_data):
    placeholder = slide.placeholders[placeholder_id]
    return placeholder.insert_chart(chart_type, chart_data)


def _add_image_or_text(slide, placeholder_id, image_url_or_text, original_image_size):
    if os_util.is_image(image_url_or_text):
        return _add_image(slide, placeholder_id, image_url_or_text, original_image_size)
    else:
        return _add_text(slide, placeholder_id, image_url_or_text)


def _print_all_placeholders(slide):
    for shape in slide.placeholders:
        print("%d %s" % (shape.placeholder_format.idx, shape.name))


def add_sources_note(slide, credits: Sequence[Sequence[CreditPart]]):
    """Credit the image sources on the slide. Each credit is a sequence of (text, link) parts, so that it can
    link to its pages (the photographer, the photo, the post, Unsplash...)."""
    if not credits:
        return None
    text_frame = slide.placeholders[SOURCES_PLACEHOLDER].text_frame
    text_frame.text = "[Image sources: "
    paragraph = text_frame.paragraphs[0]
    for index, credit in enumerate(credits):
        if index:
            paragraph.add_run().text = ", "
        for text, url in credit:
            run = paragraph.add_run()
            run.text = text
            if url:
                run.hyperlink.address = url
    paragraph.add_run().text = "]"
    return True


# FORMAT GENERATORS
# These are functions that get some inputs (texts, images...)
# and create layouted slide with these inputs


def create_new_powerpoint() -> Presentation:
    return pptx.Presentation(get_powerpoint_template_file())


def create_title_slide(prs, title, subtitle):
    slide = _create_slide(prs, LAYOUT_TITLE_SLIDE)
    _add_title(slide, title)
    _add_text(slide, 1, subtitle)
    return slide


def create_large_quote_slide(prs, title, text, background_image=None):
    if bool(text):
        slide = _create_slide(prs, LAYOUT_LARGE_QUOTE)
        if title:
            _add_title(slide, title)
        _add_text(slide, 1, text)
        if background_image:
            _add_image(slide, 11, background_image, False)

        # Add black transparent image for making other image behind it transparent (missing feature in python-pptx)
        data_folder = Path(__file__).parent.parent / "data" / "images" / "black-transparent.png"
        _add_image(slide, 12, ImageData(str(data_folder.absolute())), False)

        return slide


def create_image_slide(prs, title=None, image_url=None, original_image_size=True):
    """Creates a slide with an image covering the whole slide"""
    # TODO debug this: the image can not be set!
    return _create_single_image_slide(prs, title, image_url, LAYOUT_TITLE_AND_PICTURE, original_image_size)


def create_full_image_slide(prs, title=None, image_url=None, original_image_size=True):
    """Creates a slide with an image covering the whole slide"""
    return _create_single_image_slide(prs, title, image_url, LAYOUT_FULL_PICTURE, original_image_size)


def create_two_column_images_slide(
    prs,
    title=None,
    caption_1=None,
    image_or_text_1=None,
    caption_2=None,
    image_or_text_2=None,
    original_image_size=True,
):
    # if _is_valid_content(image_or_text_1) and _is_valid_content(image_or_text_2):
    slide = _create_slide(prs, LAYOUT_TWO_TITLE_AND_IMAGE)
    _add_title(slide, title)
    _add_text(slide, 1, caption_1)
    _add_image_or_text(slide, 13, image_or_text_1, original_image_size)
    _add_text(slide, 3, caption_2)
    _add_image_or_text(slide, 14, image_or_text_2, original_image_size)
    return slide


def create_three_column_images_slide(
    prs,
    title=None,
    caption_1=None,
    image_or_text_1=None,
    caption_2=None,
    image_or_text_2=None,
    caption_3=None,
    image_or_text_3=None,
    original_image_size=True,
):
    # if (
    #     _is_valid_content(image_or_text_1)
    #     and _is_valid_content(image_or_text_2)
    #     and _is_valid_content(image_or_text_3)
    # ):
    slide = _create_slide(prs, LAYOUT_THREE_TITLE_AND_IMAGE)
    _add_title(slide, title)
    _add_text(slide, 1, caption_1)
    _add_image_or_text(slide, 13, image_or_text_1, original_image_size)
    _add_text(slide, 3, caption_2)
    _add_image_or_text(slide, 14, image_or_text_2, original_image_size)
    _add_text(slide, 15, caption_3)
    _add_image_or_text(slide, 16, image_or_text_3, original_image_size)
    return slide


# def create_two_column_images_slide_text_second(prs, title=None, caption_1=None, image_1=None, caption_2=None,
#                                                quote=None,
#                                                original_image_size=True):
#     if bool(image_1):
#         slide = _create_slide(prs, LAYOUT_TWO_TITLE_AND_IMAGE)
#         _add_title(slide, title)
#         _add_text(slide, 1, caption_1)
#         _add_image_or_text(slide, 13, image_1, original_image_size)
#         _add_text(slide, 3, caption_2)
#         _add_image_or_text(slide, 14, quote)
#         return slide


def _create_single_image_slide(prs, title, image_url, slide_template_idx, fit_image):
    # if _is_valid_content(image_url):
    slide = _create_slide(prs, slide_template_idx)
    _add_title(slide, title)
    _add_image_or_text(slide, 1, image_url, fit_image)
    return slide


def create_chart_slide(prs, title, chart_type, chart_data, chart_modifier=None):
    slide = _create_slide(prs, LAYOUT_TITLE_AND_CHART)
    _add_title(slide, title)
    chart = _add_chart(slide, 10, chart_type, chart_data).chart
    if chart_modifier:
        chart_modifier(chart, chart_data)
    return slide
