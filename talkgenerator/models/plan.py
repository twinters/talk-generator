"""The plan format: what a talk says, before it has images and a layout (docs/v5-plan.md, sections 4 to 6).

A plan is what a language model or an agent (Claude, through the Skill) writes, and what the realizer turns into
slides: for every slide its kind (a slide shape, such as two captioned images), what it's about (its concept), its
texts, and a search query for each of its images. Plans hold queries, never image addresses: finding, licensing and
crediting images stays with talkgenerator. And the presenter's name never goes into a plan: it's filled in locally.

`talkgenerator schema plan` prints the JSON Schema of this format, and `talkgenerator formats --details` the slide
kinds, their texts and images, and the recipes to pick from.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data

PLAN_VERSION: Final = 1


class SlidePlan(Data):
    kind: str = Field(description="The slide's shape, such as 'two_columns' (see `talkgenerator formats --details`).")
    recipe: str | None = Field(
        default=None,
        description="Which look and image sources to use for this kind of slide, such as 'two-captions-gifs' (see "
        "`talkgenerator formats --details`); without one, the kind's default. Also what makes the slide when it "
        "can't be made as planned.",
    )
    concept: str = Field(
        default="",
        description="What the slide is about, as a search of one to three words, such as 'medieval bread'. An image "
        "whose own query finds nothing is searched for with it.",
    )
    texts: dict[str, str] = Field(
        default_factory=dict, description="The slide's texts, by the names its kind gives them (such as 'title')."
    )
    images: dict[str, str] = Field(
        default_factory=dict,
        description="A search query for each of the slide's images, by the names its kind gives them (such as "
        "'image_1'): a few plain English words saying what the image shows. Or the path of an image file of your "
        "own. Never an image's address: talkgenerator finds, licenses and credits the images.",
    )


class TalkPlan(Data):
    plan_version: Literal[1] = Field(default=PLAN_VERSION, description="The version of this plan format.")
    format: str | None = Field(
        default=None,
        description="The talk format, such as 'ted' for copyright-free images only (see `talkgenerator formats`); "
        "without one, 'default'. Its slide kinds and recipes are the ones a plan can use.",
    )
    topic: str = Field(description="What the talk is about, such as 'peanuts'.")
    language: str = Field(default="en", description="The language of the talk's texts, such as 'en' or 'nl'.")
    title: str = Field(description="The talk's title, on its title slide (at most 80 characters).")
    presenter_job: str = Field(
        default="",
        description="The presenter's grand, made-up job (at most 40 characters). The title slide reads 'By "
        "<name>, <job>': talkgenerator adds the name, which is never in a plan.",
    )
    thesis: str = Field(default="", description="The talk's absurd claim in one sentence, which the slides build on.")
    slides: tuple[SlidePlan, ...] = Field(
        default=(), description="The slides after the title slide (which is made from the title), in order."
    )
