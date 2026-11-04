import logging

from talkgenerator.slide import powerpoint_slide_creator

logger = logging.getLogger("talkgenerator")


class Slide:
    """Class representing a slide object that could be used to export to Powerpoint pptx or other representations later"""

    def __init__(self, type_name: str, ppt_slide_creator, arguments: dict):
        self._type_name = type_name
        self._ppt_slide_creator = ppt_slide_creator
        self._arguments = arguments
        self._note = ""
        self._sources = []

    def add_source(self, source: str):
        if source is not None:
            self._sources.append(source)

    def set_note(self, note: str):
        """Debug information about how the slide was generated."""
        self._note = note

    def create_powerpoint_slide(self, prs, debug_notes: bool = False):
        """Add this slide to the presentation. With debug_notes, the speaker notes explain how it was generated
        (off by default: presenters see the notes, and they spoil the surprise)."""
        ppt_slide = self._ppt_slide_creator(prs, **self._arguments)
        try:
            if ppt_slide:
                if debug_notes and self._note:
                    ppt_slide.notes_slide.notes_text_frame.text = self._note

                if len(self._sources):
                    powerpoint_slide_creator.add_sources_note(ppt_slide, self._sources)

                powerpoint_slide_creator.remove_empty_placeholders(ppt_slide)

        except (AttributeError, KeyError) as e:
            logger.error("Error while finishing slide: {}".format(e))
        return ppt_slide

    def to_slide_dictionary(self) -> dict:
        slide_dict = dict(self._arguments)
        slide_dict["type"] = self._type_name
        slide_dict["sources"] = self._sources
        return slide_dict


class TitleSlide(Slide):
    def __init__(self, title: str, subtitle: str):
        super().__init__(
            type_name="title",
            ppt_slide_creator=powerpoint_slide_creator.create_title_slide,
            arguments={"title": title, "subtitle": subtitle},
        )


class LarqeQuoteSlide(Slide):
    def __init__(self, title: str, text: str, background_image=None):
        super().__init__(
            type_name="large_quote",
            ppt_slide_creator=powerpoint_slide_creator.create_large_quote_slide,
            arguments={
                "title": title,
                "text": text,
                "background_image": background_image,
            },
        )


class ImageSlide(Slide):
    def __init__(self, title=None, image_url=None, original_image_size=True):
        super().__init__(
            type_name="image",
            ppt_slide_creator=powerpoint_slide_creator.create_image_slide,
            arguments={
                "title": title,
                "image_url": image_url,
                "original_image_size": original_image_size,
            },
        )


class FullImageSlide(Slide):
    def __init__(self, title=None, image_url=None, original_image_size=True):
        super().__init__(
            type_name="full_image",
            ppt_slide_creator=powerpoint_slide_creator.create_full_image_slide,
            arguments={
                "title": title,
                "image_url": image_url,
                "original_image_size": original_image_size,
            },
        )


class TwoColumnImageSlide(Slide):
    def __init__(
        self,
        title=None,
        caption_1=None,
        image_or_text_1=None,
        caption_2=None,
        image_or_text_2=None,
        original_image_size=True,
    ):
        super().__init__(
            type_name="two_column_image",
            ppt_slide_creator=powerpoint_slide_creator.create_two_column_images_slide,
            arguments={
                "title": title,
                "caption_1": caption_1,
                "image_or_text_1": image_or_text_1,
                "caption_2": caption_2,
                "image_or_text_2": image_or_text_2,
                "original_image_size": original_image_size,
            },
        )


class ThreeColumnImageSlide(Slide):
    def __init__(
        self,
        title=None,
        caption_1=None,
        image_or_text_1=None,
        caption_2=None,
        image_or_text_2=None,
        caption_3=None,
        image_or_text_3=None,
        original_image_size=True,
    ):
        super().__init__(
            type_name="three_column_image",
            ppt_slide_creator=powerpoint_slide_creator.create_three_column_images_slide,
            arguments={
                "title": title,
                "caption_1": caption_1,
                "image_or_text_1": image_or_text_1,
                "caption_2": caption_2,
                "image_or_text_2": image_or_text_2,
                "caption_3": caption_3,
                "image_or_text_3": image_or_text_3,
                "original_image_size": original_image_size,
            },
        )


class ChartSlide(Slide):
    def __init__(self, title, chart_type, chart_data, chart_modifier=None):
        super().__init__(
            type_name="chart",
            ppt_slide_creator=powerpoint_slide_creator.create_chart_slide,
            arguments={
                "title": title,
                "chart_type": chart_type,
                "chart_data": chart_data,
                "chart_modifier": chart_modifier,
            },
        )
