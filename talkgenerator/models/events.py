"""The events of a talk while it's made (talkgenerator.generator.stream_talk), in this order: talk.started, a
slide.ready for every slide, one more for its closer (the slide after its last, marked as the closer: D76), and
talk.finished, with the whole deck. In a talk that generates pictures, a slide can
come again, as slide.updated, once a generated picture takes the place of its stock photo: whenever that comes in,
after the slide's slide.ready and before talk.finished; in a talk with a time limit per slide, a slide that ran out of
time can come after all (a slide.updated that's late) in place of what stood in for it. A talk that asks for spares
gets slide.spare events too, in between: slides to show while the next slide isn't in yet, which aren't the talk's
(see SlideSpare); one that asks for early versions of its last slides gets a slide.early for each, before that
slide's slide.ready (see SlideEarly); and one that asks for its progress gets talk.progress events, from its very start
(before talk.started) until it's finished: how far it is, whenever that changes (see TalkProgress).

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
    slides: int  # how many slides it's to have (a slide that can't be made is left out), not counting its closer
    theme: str = "classic"  # the theme's name: "classic" (the 2019 template), or one of a family's
    style: Theme | None = None  # the theme's tokens (none for the classic theme)
    # The language model that writes it, as "provider:model" (the one asked; the finished deck names the one that
    # answered), or none: a classic talk
    language_model: str | None = None


class SlideReady(_Event):
    """A slide, settled, and in a themed talk laid out (every element in its box, as in the finished deck). The last
    one is the talk's closer (its slide's closer is true: D76), after the slides it asked for."""

    event: Literal["slide.ready"] = "slide.ready"
    index: int  # its place in the deck, from 0
    slide: DeckSlide


class SlideUpdated(_Event):
    """A slide handed over before, again, laid out as it was: with a picture that came in later (a generated one, in
    the place of the stock photo it had: see talkgenerator.images.generation). It takes the place of the slide at its
    index. Or, late, a whole other slide: in a talk with a time limit per slide (see stream_talk's slide_seconds), the
    real slide, which ran out of time and came after all, in place of what stood in for it."""

    event: Literal["slide.updated"] = "slide.updated"
    index: int  # its place in the deck, from 0, as its slide.ready said
    slide: DeckSlide
    # True for a slide that came after all, in place of what stood in for it (whoever shows the slide at its index may
    # rather keep showing that until they go on); none for a slide with a picture that came in later
    late: bool | None = None


class SlideSpare(_Event):
    """A spare slide: one to show while the talk's next slide isn't in yet, when a presenter catches up with the
    making (see stream_talk's spares). It's on the talk's topic and laid out in its theme, without a slide number, and
    made quickly, early on. It's none of the talk's slides: it has no place in the deck, and the finished deck (and so
    its PowerPoint) leaves it out."""

    event: Literal["slide.spare"] = "slide.spare"
    index: int  # which spare it is, from 0, in the order they come (not a place in the deck)
    slide: DeckSlide


class SlideEarly(_Event):
    """An early version of one of the talk's slides (see stream_talk's early): a quick slide about that slide's own
    topic, laid out in the talk's theme and numbered as that slide, made early on, for a presentation to show when it
    reaches that place before the slide is in. It comes before the slide's slide.ready, which takes its place. It's
    none of the talk's slides, unless the slide runs out of time or can't be made: then the early version is the slide
    (its slide.ready brings it, laid out where it stands)."""

    event: Literal["slide.early"] = "slide.early"
    index: int  # the place of the slide it's an early version of, from 0, as that slide's slide.ready will say
    slide: DeckSlide


# Where a talk is while it's made, and where each of its slides is (see TalkProgress)
TalkStage = Literal["starting", "asking", "planning", "writing", "composing", "finishing"]
SlideStage = Literal["waiting", "planned", "written", "ready"]


class TalkProgress(_Event):
    """How far the talk is while it's made, for a talk that asks for it (see stream_talk's progress): sent whenever
    that changes, whole, so that the last one says it all. It's no slide, and the deck has none of it.

    stage is where the talk is: starting (its persona, format, theme and its slides' words are being picked); asking (a
    language model writes it, and was asked, but hasn't answered yet: a free model can take a while); planning (the
    model's plan comes in: the talk's title, the presenter's job and name, its thesis, and at the Advanced level every
    slide's word and idea); writing (the model writes the slides' texts); composing (the slides are made, their pictures
    looked up, and handed over in order, slide.ready); and finishing (every slide is in, and the talk waits for what
    comes after its slides: generated pictures, a vision pick, a slide that ran out of time). A classic talk goes from
    starting to composing. A model that's asked again (when it found the topic unsafe, or answered in English in a talk
    in another language) takes the talk back to asking.

    slides is every slide's own stage, by its number (from 0): waiting; planned (its idea is in, at the Advanced level);
    written (the model wrote its texts, and its pictures are being looked up); or ready (handed over). A slide the model
    doesn't write (the title slide, a classic slide) goes from waiting to ready. parts counts the parts of the model's
    plan that came in (the fields of its spine, and at the Advanced level the slides' ideas), writes how many slides the
    model writes, and written how many of those it wrote so far (ready ones too)."""

    event: Literal["talk.progress"] = "talk.progress"
    stage: TalkStage
    slides: tuple[SlideStage, ...]
    parts: int = 0
    writes: int = 0
    written: int = 0


class TalkFinished(_Event):
    """The talk is done: the whole deck, as generate_presentation makes it, with what it asked of language models and
    image generators."""

    event: Literal["talk.finished"] = "talk.finished"
    deck: Deck


TalkEvent = Annotated[
    TalkStarted | SlideReady | SlideUpdated | SlideSpare | SlideEarly | TalkProgress | TalkFinished,
    Field(discriminator="event"),
]
