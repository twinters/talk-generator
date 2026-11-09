"""The events of a talk while it's made (talkgenerator.generator.stream_talk), in this order: talk.started, a
slide.ready for every slide, and talk.finished, with the whole deck. In a talk that generates pictures, a slide can
come again, as slide.updated, once a generated picture takes the place of its stock photo: whenever that comes in,
after the slide's slide.ready and before talk.finished. A talk that asks for spares gets slide.spare events too, in
between: slides to show while the next slide isn't in yet, which aren't the talk's (see SlideSpare).

They're plain data, as Server-Sent Events carry them: an event's `event` is its name, and to_json() is its data (the
deck format's elements, as in talkgenerator.models.deck). A browser can draw a themed talk's slides as they come in,
since each comes laid out in the talk's theme, whose tokens talk.started brings.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from talkgenerator.models.base import Data
from talkgenerator.models.deck import Deck, DeckSlide, TalkPersona, TopicOrTitle
from talkgenerator.models.theme import Theme


class _Event(Data):
    def to_json(self) -> str:
        """The event's data, as one line of JSON (without what's empty)."""
        return self.model_dump_json(exclude_none=True)


class TalkStarted(_Event):
    """The talk is under way: what it's called (the title it settled on), who presents it (their name, and the persona
    the talk's dice picked for them), in which language, and how it looks."""

    event: Literal["talk.started"] = "talk.started"
    title: str | None = None
    presenter: str | None = None
    persona: TalkPersona | None = None  # (as in the deck)
    topics: tuple[str, ...] = ()
    # What was typed, when it could be the topic or the title, and how it was read (as in the deck)
    topic_or_title: TopicOrTitle | None = None
    language: str = "en"
    seed: int | None = None
    slides: int  # how many slides it's to have (a slide that can't be made is left out)
    theme: str = "classic"  # the theme's name: "classic" (the 2019 template), or one of a family's
    style: Theme | None = None  # the theme's tokens (none for the classic theme)
    # The language model that writes it, as "provider:model" (the one asked; the finished deck names the one that
    # answered), or none: a classic talk
    language_model: str | None = None


class SlideReady(_Event):
    """A slide, settled, and in a themed talk laid out (every element in its box, as in the finished deck)."""

    event: Literal["slide.ready"] = "slide.ready"
    index: int  # its place in the deck, from 0
    slide: DeckSlide


class SlideUpdated(_Event):
    """A slide handed over before, again, laid out as it was: with a picture that came in later (a generated one, in
    the place of the stock photo it had: see talkgenerator.images.generation). It takes the place of the slide at its
    index."""

    event: Literal["slide.updated"] = "slide.updated"
    index: int  # its place in the deck, from 0, as its slide.ready said
    slide: DeckSlide


class SlideSpare(_Event):
    """A spare slide: one to show while the talk's next slide isn't in yet, when a presenter catches up with the
    making (see stream_talk's spares). It's on the talk's topic and laid out in its theme, without a slide number, and
    made quickly, early on. It's none of the talk's slides: it has no place in the deck, and the finished deck (and so
    its PowerPoint) leaves it out."""

    event: Literal["slide.spare"] = "slide.spare"
    index: int  # which spare it is, from 0, in the order they come (not a place in the deck)
    slide: DeckSlide


class TalkFinished(_Event):
    """The talk is done: the whole deck, as generate_presentation makes it, with what it asked of language models and
    image generators."""

    event: Literal["talk.finished"] = "talk.finished"
    deck: Deck


TalkEvent = Annotated[TalkStarted | SlideReady | SlideUpdated | SlideSpare | TalkFinished, Field(discriminator="event")]
