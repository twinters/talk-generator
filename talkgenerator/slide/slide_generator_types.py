import logging
from collections.abc import Callable
from typing import Any

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import analysis
from talkgenerator.slide import slides
from talkgenerator.util import generator_util

logger = logging.getLogger("talkgenerator")


class SlideGenerator:
    """Makes slides of one Slide class (slide_type) from a content generator: a function of the presentation context
    that gives the class's arguments, in their order."""

    slide_type: Callable[..., slides.Slide]

    def __init__(self, slide_content_generator):
        self._slide_content_generator = slide_content_generator

    @classmethod
    def of(cls, *generators):
        """From a generator of each of the Slide class's arguments, in their order."""
        return cls(CombinedSlideGenerator(*generators))

    def generate_slide(self, presentation_context, used) -> tuple[slides.Slide, list] | None:
        """Generates the slide using the given generators.

        Returns None when the content repeats too much of what's used already, or when the slide misses
        content (say, an image that no source could deliver), so that it's tried again or another kind of
        slide takes its place instead of leaving a hole in the deck."""
        logger.debug("slide_generator_types.generate_slide")
        logger.debug(f"presentation_context: {presentation_context}")
        logger.debug(f"self._slide_content_generator: {self._slide_content_generator}")
        generated = self._slide_content_generator(presentation_context)
        logger.debug(f"generated: {generated}")
        # (a diagram's pictures, after its other arguments, go to the slide by name: they're among what it's made of)
        pictures: dict[str, ImageData] = {}
        if isinstance(generated, tuple | list) and generated and isinstance(generated[-1], slides.Pictures):
            pictures = generated[-1].by_box()
            generated = [*generated[:-1], *pictures.values()]
            arguments = generated[: len(generated) - len(pictures)]
        else:
            arguments = generated
        if not is_different_enough(generated, used):
            return None
        slide = self.slide_type(*arguments, pictures=pictures) if pictures else self.slide_type(*arguments)
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


# The last argument of the Slide classes that show images: that they're shown whole (original_image_size). v4's slide
# generators made it with the rest of a slide's content, and none ever turned it off; it stays among what a slide
# generates, as a slide's notes list that.
_WHOLE = generator_util.StaticGenerator(True)


class TitleSlideGenerator(SlideGenerator):
    slide_type = slides.TitleSlide

    @classmethod
    def of(cls, title_generator, subtitle_generator):
        return cls(CombinedSlideGenerator(title_generator, subtitle_generator))


class LarqeQuoteSlideGenerator(SlideGenerator):
    slide_type = slides.LarqeQuoteSlide

    @classmethod
    def of(cls, title_generator, text_generator, background_image_generator):
        return cls(CombinedSlideGenerator(title_generator, text_generator, background_image_generator))


class ImageSlideGenerator(SlideGenerator):
    slide_type = slides.ImageSlide

    @classmethod
    def of(cls, title_generator, image_generator=None):
        return cls(CombinedSlideGenerator(title_generator, image_generator, _WHOLE))

    @classmethod
    def of_tupled_captioned_image(cls, tuple_generator):
        """From one generator of its (title, image) tuple."""
        return cls(_tupled_captioned_images(None, tuple_generator))


class FullImageSlideGenerator(SlideGenerator):
    slide_type = slides.FullImageSlide

    @classmethod
    def of(cls, title_generator, image_generator=None):
        return cls(CombinedSlideGenerator(title_generator, image_generator, _WHOLE))


class _ColumnsSlideGenerator(SlideGenerator):
    """A slide of columns, each a caption over an image (or a text)."""

    @classmethod
    def of_tupled_captioned_images(cls, title_generator, *tuple_generators):
        """From a generator of its title, and one of each column's (caption, image) tuple."""
        return cls(_tupled_captioned_images(title_generator, *tuple_generators))

    @classmethod
    def of_images_and_tupled_captions(cls, title_generator, captions_generator, *image_generators):
        """From a generator of its title, one of all its columns' captions, and one of each column's image."""
        return cls(_images_and_tupled_captions(title_generator, captions_generator, *image_generators))


class TwoColumnImageSlideGenerator(_ColumnsSlideGenerator):
    slide_type = slides.TwoColumnImageSlide

    @classmethod
    def of(
        cls,
        title_generator,
        caption_1_generator,
        image_or_text_1_generator,
        caption_2_generator,
        image_or_text_2_generator,
    ):
        return cls(
            CombinedSlideGenerator(
                title_generator,
                caption_1_generator,
                image_or_text_1_generator,
                caption_2_generator,
                image_or_text_2_generator,
                _WHOLE,
            )
        )


class ThreeColumnImageSlideGenerator(_ColumnsSlideGenerator):
    slide_type = slides.ThreeColumnImageSlide

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
                _WHOLE,
            )
        )


def _tupled_captioned_images(title_generator, *tuple_generators):
    """The content of a slide whose captions and images come together, a (caption, image) tuple from one generator
    each (an "about me" slide's hobby and its picture): the tuples first, then the title (none without a title
    generator: a slide of one image, whose caption is its title), as v4 made them."""

    def content(presentation_context):
        tuples = [generator(presentation_context) for generator in tuple_generators]
        title = [title_generator(presentation_context)] if title_generator is not None else []
        return (*title, *(element for made in tuples for element in (made[0], made[1])), True)

    return content


def _images_and_tupled_captions(title_generator, captions_generator, *image_generators):
    """The content of a slide of columns whose captions come together, from one generator (the parts of one line,
    such as an expectation and the reality), over an image each: the captions first, then the title, then the
    images, as v4 made them."""

    def content(presentation_context):
        captions = captions_generator(presentation_context)
        title = title_generator(presentation_context)
        images = [generator(presentation_context) for generator in image_generators]
        return (title, *(element for index, image in enumerate(images) for element in (captions[index], image)), True)

    return content


class ChartSlideGenerator(SlideGenerator):
    """A chart, from a generator of its title, its type, its data and what else its Slide class takes (see
    talkgenerator.sources.chart)."""

    slide_type = slides.ChartSlide


class DiagramSlideGenerator(SlideGenerator):
    """A diagram drawn as shapes (a Venn diagram, a 2×2 matrix), from a generator of its title and its diagram."""

    slide_type = slides.DiagramSlide


class DrawnSlideGenerator(SlideGenerator):
    """A slide of one of milestone 6's types (a big number, a quiz, a post...: see slides.DrawnSlide), from a
    generator of its Slide class's arguments (see talkgenerator.sources.slide_texts)."""

    def __init__(self, slide_content_generator, slide_class: type[slides.DrawnSlide]):
        super().__init__(slide_content_generator)
        self.slide_type = slide_class


class PictureFirstSlideGenerator:
    """A classic chart or diagram that's a picture in its place now and then, under its title (docs/v5-plan.md, D73):
    its text version first, from the slide generator it wraps (text), and then, as the dice say (that share of the
    time: odds), a picture of the look's (picture: an image slot, such as Reddit's bad charts), found for the slide's
    seed, filling the slide under the text version's title (or its question); the text version as it is when none is
    found, or the dice say no, or it has no title. The text version's draws come first, so it comes out the same with
    pictures first or without; and it's what stands in for it in a talk with a time limit per slide, until its picture
    comes (see PresentationSchema._generate_slides). DISABLE_PICTURE_FIRST switches the pictures off."""

    def __init__(self, text: SlideGenerator, picture: Callable[[dict[str, Any]], Any], odds: float):
        self.text = text
        self.picture = picture
        self.odds = odds

    def generate_slide(self, presentation_context, used) -> tuple[slides.Slide, list] | None:
        from talkgenerator.plan.kinds import pictures_first  # (the kinds build slides of this module's types)
        from talkgenerator.util import random_util

        made = self.text.generate_slide(presentation_context, used)
        if made is None or not pictures_first() or random_util.random() >= self.odds:
            return made
        title = made[0].picture_title()
        if not title:
            return made
        # (not one of the talk's pictures so far, where the picture's source can avoid them: an image slot)
        seed = presentation_context.get("seed")
        avoid = [element for element in used[0] if isinstance(element, ImageData)]
        find = getattr(self.picture, "find", None)
        picture = (
            find(str(seed), avoid=avoid) if find is not None and seed else self.picture(dict(presentation_context))
        )
        if not isinstance(picture, ImageData) or not is_different_enough([title, picture], used):
            return made
        slide = slides.FullImageSlide(title, picture)
        if slide.missing_content():
            return made
        slide.add_note(f"Picture first: in place of its {made[0].type_name}, under its title")
        return slide, [title, picture]


# HELPERS


class CombinedSlideGenerator:
    def __init__(self, *generators):
        self._generators = generators

    def __call__(self, presentation_context):
        return [
            content_generator(presentation_context) if content_generator else None
            for content_generator in self._generators
        ]


def is_different_enough(generated, used):
    (used_elements, allowed_repeated_elements) = used
    return is_different_enough_for_allowed_repeated(generated, used_elements, allowed_repeated_elements)


def is_different_enough_for_allowed_repeated(generated, used_elements, allowed_repeated_elements):
    """Whether the generated elements repeat no more of the used ones than allowed, and no image (nor nearly the same
    image): a slide may repeat texts (conclusions sum up), but a picture twice is a picture too few. (The schema
    settles slides by the same rule, so generating them in parallel gives what generating them one by one does.)"""
    if generated:
        if not used_elements:
            return True
        if any(
            isinstance(element, ImageData) and (element in used_elements or nearly_used(element, used_elements))
            for element in generated
        ):
            return False
        return allowed_repeated_elements >= len(set(generated) & used_elements)
    return False


def nearly_used(image: ImageData, used_elements) -> bool:
    """Whether an image is nearly the same as one of the used images (by what a look at both found)."""
    if image.analysis is None:
        return False
    return any(
        isinstance(element, ImageData) and analysis.near_duplicates(image.analysis, element.analysis)
        for element in used_elements
    )
