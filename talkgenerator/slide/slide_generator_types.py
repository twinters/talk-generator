import logging
from abc import ABCMeta, abstractmethod

from talkgenerator.slide import slides
from talkgenerator.util import generator_util

logger = logging.getLogger("talkgenerator")


class SlideGenerator(metaclass=ABCMeta):
    """Generating Slide objects using a list of generators"""

    def __init__(self, slide_content_generator):
        """The given content_providers is a function that when called,
        generates all of the arguments for the slide creator"""
        self._slide_content_generator = slide_content_generator

    @property
    @abstractmethod
    def slide_type(self):
        """The function converting it to a Slide object"""
        pass

    @classmethod
    def of(cls, *generators):
        return cls(CombinedSlideGenerator(*generators))

    def generate_slide(self, presentation_context, used) -> tuple[slides.Slide, list] | None:
        """Generates the slide using the given generators.

        Returns None when the content repeats too much of what's used already, or when the slide misses
        content (say, an image that no source could deliver), so that it's tried again or another kind of
        slide takes its place instead of leaving a hole in the deck."""
        logger.debug("slide_generator_types.generate_slide")
        logger.debug("presentation_context: {}".format(presentation_context))
        logger.debug("self._slide_content_generator: {}".format(self._slide_content_generator))
        generated = self._slide_content_generator(presentation_context)
        logger.debug("generated: {}".format(generated))
        if not is_different_enough(generated, used):
            return None
        slide = self.slide_type(*generated)
        missing = slide.missing_content()
        if missing:
            logger.info(
                "No usable %s for a %s slide about '%s'",
                " or ".join(missing),
                slide.type_name,
                presentation_context.get("seed"),
            )
            return None
        return slide, generated


class TitleSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(cls, title_generator, subtitle_generator):
        return cls(CombinedSlideGenerator(title_generator, subtitle_generator))

    @property
    def slide_type(self):
        return slides.TitleSlide


class LarqeQuoteSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(cls, title_generator, text_generator, background_image_generator):
        return cls(CombinedSlideGenerator(title_generator, text_generator, background_image_generator))

    @property
    def slide_type(self):
        return slides.LarqeQuoteSlide


class ImageSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(cls, title_generator, image_generator=None, original_image_size=True):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                image_generator,
                generator_util.StaticGenerator(original_image_size),
            )
        )

    @classmethod
    def of_tupled_captioned_image(cls, tuple_1_generator, original_image_size=True):
        return cls(TupledCaptionedImageGenerator(tuple_1_generator, original_image_size))

    @property
    def slide_type(self):
        return slides.ImageSlide


class TupledCaptionedImageGenerator:
    def __init__(self, tuple_1_generator, original_image_size=True):
        self._tuple_1_generator = tuple_1_generator
        self._original_image_size = original_image_size

    def __call__(self, presentation_context):
        generated_tuple_1 = self._tuple_1_generator(presentation_context)
        return generated_tuple_1[0], generated_tuple_1[1], self._original_image_size


class FullImageSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(cls, title_generator, image_generator=None, original_image_size=True):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                image_generator,
                generator_util.StaticGenerator(original_image_size),
            )
        )

    @property
    def slide_type(self):
        return slides.FullImageSlide


class TwoColumnImageSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(
        cls,
        title_generator,
        caption_1_generator,
        image_or_text_1_generator,
        caption_2_generator,
        image_or_text_2_generator,
        original_image_size=True,
    ):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                caption_1_generator,
                image_or_text_1_generator,
                caption_2_generator,
                image_or_text_2_generator,
                generator_util.StaticGenerator(original_image_size),
            )
        )

    @classmethod
    def of_tupled_captioned_images(
        cls,
        title_generator,
        tuple_1_generator,
        tuple_2_generator,
        original_image_size=True,
    ):
        return cls(
            TwoTupledCaptionedImagesGenerator(
                title_generator,
                tuple_1_generator,
                tuple_2_generator,
                original_image_size,
            )
        )

    @classmethod
    def of_images_and_tupled_captions(
        cls,
        title_generator,
        captions_generator,
        image_1_generator,
        image_2_generator,
        original_image_size=True,
    ):
        return cls(
            TwoImagesAndTupledCaptions(
                title_generator,
                captions_generator,
                image_1_generator,
                image_2_generator,
                original_image_size,
            )
        )

    @property
    def slide_type(self):
        return slides.TwoColumnImageSlide


class TwoTupledCaptionedImagesGenerator(SlideGenerator):
    def __init__(
        self,
        title_generator,
        tuple_1_generator,
        tuple_2_generator,
        original_image_size=True,
    ):
        super().__init__(self)
        self._title_generator = title_generator
        self._tuple_1_generator = tuple_1_generator
        self._tuple_2_generator = tuple_2_generator
        self._original_image_size = original_image_size

    def __call__(self, presentation_context):
        generated_tuple_1 = self._tuple_1_generator(presentation_context)
        generated_tuple_2 = self._tuple_2_generator(presentation_context)
        return (
            self._title_generator(presentation_context),
            generated_tuple_1[0],
            generated_tuple_1[1],
            (generated_tuple_2[0]),
            generated_tuple_2[1],
            self._original_image_size,
        )

    @property
    def slide_type(self):
        return slides.TwoColumnImageSlide


class TwoImagesAndTupledCaptions(SlideGenerator):
    def __init__(
        self,
        title_generator,
        captions_generator,
        image_1_generator,
        image_2_generator,
        original_image_size=True,
    ):
        super().__init__(self)
        logger.debug("initializing TwoImagesAndTupledCaptions")
        self._title_generator = title_generator
        self._captions_generator = captions_generator
        self._image_1_generator = image_1_generator
        self._image_2_generator = image_2_generator
        self._original_image_size = original_image_size

    def __call__(self, presentation_context):
        logger.debug("Calling TwoImagesAndTupledCaptions")
        logger.debug("**********************************")
        logger.debug("presentation_context: {}".format(presentation_context))
        logger.debug("captions_generator: {}".format(self._captions_generator))
        logger.debug("original_image_size: {}".format(self._original_image_size))

        generated_tuple = self._captions_generator(presentation_context)
        logger.debug("generated_tuple: {}".format(generated_tuple))

        logger.debug("title_generator: {}".format(self._title_generator))
        _title = self._title_generator(presentation_context)
        logger.debug("_title: {}".format(_title))

        logger.debug("image_1_generator: {}".format(self._image_1_generator))
        _image1 = self._image_1_generator(presentation_context)
        logger.debug("_image1: {}".format(_image1))

        logger.debug("image_2_generator: {}".format(self._image_2_generator))
        _image2 = self._image_2_generator(presentation_context)
        logger.debug("_image2: {}".format(_image2))

        return (
            _title,
            generated_tuple[0],
            _image1,
            generated_tuple[1],
            _image2,
            self._original_image_size,
        )

    @property
    def slide_type(self):
        return slides.TwoColumnImageSlide


class ThreeColumnImageSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(
        cls,
        title_generator,
        caption_1_generator,
        image_or_text_1_generator,
        caption_2_generator,
        image_or_text_2_generator,
        caption_3_generator,
        image_or_text_3_generator,
        original_image_size=True,
    ):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                caption_1_generator,
                image_or_text_1_generator,
                caption_2_generator,
                image_or_text_2_generator,
                caption_3_generator,
                image_or_text_3_generator,
                generator_util.StaticGenerator(original_image_size),
            )
        )

    @classmethod
    def of_tupled_captioned_images(
        cls,
        title_generator,
        tuple_1_generator,
        tuple_2_generator,
        tuple_3_generator,
        original_image_size=True,
    ):
        return cls(
            ThreeTupledCaptionedImagesGenerator(
                title_generator,
                tuple_1_generator,
                tuple_2_generator,
                tuple_3_generator,
                original_image_size,
            )
        )

    @classmethod
    def of_images_and_tupled_captions(
        cls,
        title_generator,
        captions_generator,
        image_1_generator,
        image_2_generator,
        image_3_generator,
        original_image_size=True,
    ):
        return cls(
            ThreeImagesAndTupledCaptions(
                title_generator,
                captions_generator,
                image_1_generator,
                image_2_generator,
                image_3_generator,
                original_image_size,
            )
        )

    @property
    def slide_type(self):
        return slides.ThreeColumnImageSlide


class ThreeTupledCaptionedImagesGenerator(SlideGenerator):
    def __init__(
        self,
        title_generator,
        tuple_1_generator,
        tuple_2_generator,
        tuple_3_generator,
        original_image_size=True,
    ):
        super().__init__(self)
        self._title_generator = title_generator
        self._tuple_1_generator = tuple_1_generator
        self._tuple_2_generator = tuple_2_generator
        self._tuple_3_generator = tuple_3_generator
        self._original_image_size = original_image_size

    def __call__(self, presentation_context):
        generated_tuple_1 = self._tuple_1_generator(presentation_context)
        generated_tuple_2 = self._tuple_2_generator(presentation_context)
        generated_tuple_3 = self._tuple_3_generator(presentation_context)
        return (
            self._title_generator(presentation_context),
            generated_tuple_1[0],
            generated_tuple_1[1],
            (generated_tuple_2[0]),
            generated_tuple_2[1],
            generated_tuple_3[0],
            generated_tuple_3[1],
            self._original_image_size,
        )

    @property
    def slide_type(self):
        return slides.ThreeColumnImageSlide


class ThreeImagesAndTupledCaptions(SlideGenerator):
    def __init__(
        self,
        title_generator,
        captions_generator,
        image_1_generator,
        image_2_generator,
        image_3_generator,
        original_image_size=True,
    ):
        super().__init__(self)
        self._title_generator = title_generator
        self._captions_generator = captions_generator
        self._image_1_generator = image_1_generator
        self._image_2_generator = image_2_generator
        self._image_3_generator = image_3_generator
        self._original_image_size = original_image_size

    def __call__(self, presentation_context):
        generated_tuple = self._captions_generator(presentation_context)
        return (
            self._title_generator(presentation_context),
            generated_tuple[0],
            self._image_1_generator(presentation_context),
            generated_tuple[1],
            self._image_2_generator(presentation_context),
            generated_tuple[2],
            self._image_3_generator(presentation_context),
            self._original_image_size,
        )

    @property
    def slide_type(self):
        return slides.ThreeColumnImageSlide


class ChartSlideGenerator(SlideGenerator):
    def __init__(self, slide_content_generator):
        super().__init__(slide_content_generator)

    @classmethod
    def of(
        cls,
        title_generator,
        chart_type_generator,
        chart_data_generator,
        chart_modifier=None,
    ):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                chart_type_generator,
                chart_data_generator,
                generator_util.StaticGenerator(chart_modifier),
            )
        )

    @property
    def slide_type(self):
        return slides.ChartSlide


class DiagramSlideGenerator(SlideGenerator):
    """A diagram drawn as shapes (a Venn diagram, a 2×2 matrix), from a generator of its title and its diagram."""

    @property
    def slide_type(self):
        return slides.DiagramSlide


class DrawnSlideGenerator(SlideGenerator):
    """A slide of one of milestone 6's types (a big number, a quiz, a post...: see slides.DrawnSlide), from a
    generator of its Slide class's arguments (see talkgenerator.sources.slide_texts)."""

    def __init__(self, slide_content_generator, slide_class: type[slides.DrawnSlide]):
        super().__init__(slide_content_generator)
        self._slide_class = slide_class

    @property
    def slide_type(self):
        return self._slide_class


# HELPERS


class CombinedSlideGenerator:
    def __init__(self, *generators):
        # print("CombinedGenerator:", self, generators)
        self._generators = generators

    def __call__(self, presentation_context):
        # print("CombinedGenerator:", self)
        return [
            content_generator(presentation_context) if content_generator else None
            for content_generator in self._generators
        ]


def is_different_enough(generated, used):
    (used_elements, allowed_repeated_elements) = used
    return is_different_enough_for_allowed_repeated(generated, used_elements, allowed_repeated_elements)


def is_different_enough_for_allowed_repeated(generated, used_elements, allowed_repeated_elements):
    if generated:
        if not used_elements:
            return True
        intersection = set(generated) & used_elements
        return allowed_repeated_elements >= len(intersection)
    return False
