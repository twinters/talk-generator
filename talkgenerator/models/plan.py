"""The plan format: what a talk says, before it has images and a layout (docs/v5-plan.md, sections 4 to 6).

A plan is what a language model or an agent (Claude, through the Skill) writes, and what the realizer turns into
slides: for every slide its kind (a slide shape, such as two captioned images), what it's about (its concept), its
texts, and a search query for each of its images. Plans hold queries, never image addresses: finding, licensing and
crediting images stays with talkgenerator. And the presenter's name never goes into a plan: it's filled in locally.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data

PLAN_VERSION: Final = 1


class SlidePlan(Data):
    kind: str  # see talkgenerator.plan.kinds
    # The slide generator whose image sources (and classic fallback) to use; without one, the kind's own default
    recipe: str | None = None
    concept: str = ""  # what the slide is about: the topic of its images and of its classic fallback
    texts: dict[str, str] = Field(default_factory=dict)
    images: dict[str, str] = Field(default_factory=dict)  # search queries, by image slot


class TalkPlan(Data):
    plan_version: Literal[1] = PLAN_VERSION
    topic: str
    language: str = "en"
    title: str
    presenter_job: str = ""  # for the title slide; the presenter's name is added locally
    thesis: str = ""  # the talk's claim, which the slides build on
    slides: tuple[SlidePlan, ...] = ()
