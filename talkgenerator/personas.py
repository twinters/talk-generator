"""Who presents a talk: its persona (docs/v5-plan.md, section 5.2).

The talk's dice pick a persona, such as a disgraced professor, a startup founder or a kindergarten teacher (or the
talk names one: generate_presentation's persona), which shapes more of the talk than how the language model writes:

- its voice, in which the model writes, and the kinds of talk it gives (its angles, of which the dice pick one);
- how often each kind of slide comes up: multipliers on the format's own weights, by the slide generators' tags (see
  weight), so a medieval historian shows more history and timelines, and a startup founder more KPI tiles and funnels
  and less history. They never take a kind of slide away, and the format's caps still hold;
- the talk's title: a hint for the model on what the persona's titles are like, and title templates of its own for a
  classic talk, which half of the classic titles come from (see title_generator);
- the presenter's name (see nudge): weights over the name styles, by which the dice pick among the switched-on ones (a
  medieval historian's name is a famous-name pun more often), and for the model, how the presenter goes by (a
  professor with "Prof." before the name, a kindergarten teacher as the children call them). A talk that says which
  name styles it may have (name_styles) goes by those alone.

Classic talks get the slides, the titles and the name styles; the voice and the angle are for a language model. The
persona comes from the talk's seed (its "persona" stream), before the slides are picked, so the same seed with the same
answers gives the same talk. The deck and talk.started say which persona a talk had (see record).

Across the personas, every kind of slide comes up about as often as the format's weights say (a test keeps their
average multiplier near 1): personas move a talk's slides around, rather than change the mix of all talks.

A talk without a persona (persona "none") is the format's own: its weights and titles, the default name styles as
they are, and no voice or angle for the model. With a classic theme, classic names and no model, that's the closest
to a talk of 2019.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any, Final

from talkgenerator.models.deck import TalkPersona
from talkgenerator.names import Nudge
from talkgenerator.util import random_util

RANDOM: Final = "random"
NONE: Final = "none"  # (no persona: the format's own talk)
# How many of a classic talk's titles come from its persona's templates (the others from the format's title generator)
TITLE_SHARE: Final = 0.5
# Tags a persona never weights: every talk has its title slide, its presenter's introduction and its conclusions
UNWEIGHTED_TAGS: Final = frozenset({"title", "about_me", "conclusion"})

# A classic title generator: a presentation context (with the "seed" to make a title about) in, a title (or None) out
TitleGenerator = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class Persona:
    name: str  # what generate_presentation's persona takes, such as "startup_founder"
    label: str  # for a menu, or for a site to show: "Startup founder"
    voice: str  # who presents, for the language model: "a startup founder who has pivoted eleven times"
    angles: tuple[str, ...]  # the kinds of talk they give, for the language model: the talk's dice pick one
    # Multipliers on the format's weights of the slide generators with these tags: over 1 for the slides the persona
    # favours, under 1 for those it doesn't (1 for the tags it doesn't name)
    slides: Mapping[str, float]
    title_hint: str  # what the persona's titles are like, for the language model ("like a startup's pitch, ...")
    titles: tuple[str, ...]  # title templates for classic talks, with the topic as {seed.title}
    name_styles: Mapping[str, float]  # weights over the name styles (1 for those it doesn't name)
    name_manner: str  # how the presenter goes by, for the language model ("with Prof. before the name")

    def weight(self, tags: Iterable[str]) -> float:
        """How many times as often a slide generator with these tags comes up in the persona's talks: the product of
        their multipliers (in a fixed order, so that it's the same number in every run)."""
        factor = 1.0
        for tag in sorted(set(tags)):
            factor *= self.slides.get(tag, 1.0)
        return factor

    def angle(self, rng: random_util.Rng) -> str:
        """The angle the talk's dice pick (rng: the talk's), for the language model."""
        with random_util.use(rng.child("persona", "angle")):
            return random_util.choice(self.angles)

    @property
    def nudge(self) -> Nudge:
        """How the persona would have its presenter named (see talkgenerator.names.Nudge)."""
        return Nudge(dict(self.name_styles), self.name_manner)

    def title_generator(self, base: TitleGenerator | None) -> TitleGenerator:
        """The classic title generator of the persona's talks: one of its templates about the seed, in TITLE_SHARE of
        the talks, as the current random stream decides (the talk's "title" stream), and else base's title (None:
        none, for the talk to make its own)."""

        def generate(context: dict[str, Any]) -> Any:
            if random_util.random() < TITLE_SHARE:
                title = _templates(self.titles).generate(context)
                if title:
                    return title
            return base(context) if base is not None else None

        return generate

    def record(self, angle: str | None = None) -> TalkPersona:
        """The persona as a deck and talk.started tell it, with the angle a language model was given, if one was."""
        return TalkPersona(name=self.name, label=self.label, voice=self.voice, angle=angle)


@cache
def _templates(templates: tuple[str, ...]) -> Any:
    from talkgenerator.sources.text_generator import TemplatedTextGenerator  # (here: it loads the text sources)

    return TemplatedTextGenerator(templates_list=list(templates))


PERSONAS: Final[dict[str, Persona]] = {
    persona.name: persona
    for persona in (
        Persona(
            "disgraced_professor",
            "Disgraced professor",
            "a disgraced professor, banned from three universities, finally free to present their research",
            (
                "the research the university tried to bury",
                "why the academic establishment gets the topic all wrong",
                "a breakthrough about the topic that no journal dared to publish",
            ),
            {
                "chart": 1.8,
                "curve": 1.5,
                "diagram": 1.5,
                "quote": 1.3,
                "history": 1.3,
                "big_number": 1.3,
                "questions": 1.5,
                "full_image": 0.8,
                "gif": 0.5,
                "meme": 0.5,
                "social_post": 0.5,
                "inspiration": 0.5,
            },
            "like a lecture the university tried to cancel",
            (
                "{seed.title}: The Lecture They Tried to Cancel",
                "What My Former University Won't Tell You About {seed.title}",
                "{seed.title}: A Study No Journal Would Publish",
                "The Forbidden Science of {seed.title}",
            ),
            {"pun": 2, "famous_pun": 1.5},
            "with Prof. before the name, a title they still cling to",
        ),
        Persona(
            "startup_founder",
            "Startup founder",
            "a startup founder who has pivoted eleven times",
            (
                "a pitch for a startup that will disrupt the topic",
                "scaling the topic to a billion users",
                "what the topic taught the presenter about failing fast",
            ),
            {
                "kpi": 3,
                "big_number": 2,
                "funnel": 2.5,
                "trend_chart": 2,
                "bar_chart": 1.5,
                "chart": 1.3,
                "matrix_diagram": 1.3,
                "social_post": 1.3,
                "history": 0.3,
                "timeline": 0.7,
                "quote": 0.6,
                "anecdote": 0.7,
            },
            "like a startup's pitch, promising to disrupt something",
            (
                "Disrupting {seed.title}",
                "{seed.title} as a Service",
                "Uber, but for {seed.title}",
                "Scaling {seed.title} to a Billion Users",
            ),
            {"fun_surname": 2.5},
            "a founder's first name and surname, without Dr. or Prof.",
        ),
        Persona(
            "medieval_historian",
            "Medieval historian",
            "a medieval historian who sees the Middle Ages in everything",
            (
                "the topic's hidden medieval history",
                "what medieval monks already knew about the topic",
                "the topic as a feudal power struggle",
            ),
            {
                "history": 3,
                "timeline": 3,
                "quote": 1.5,
                "pyramid": 1.5,
                "org_chart": 1.5,
                "full_image": 1.2,
                "kpi": 0.3,
                "social_post": 0.4,
                "funnel": 0.5,
                "gif": 0.6,
            },
            "one that drags the topic back into the Middle Ages",
            (
                "{seed.title} in the Middle Ages",
                "The Forgotten Medieval History of {seed.title}",
                "{seed.title}: A Feudal Perspective",
                "What Medieval Monks Knew About {seed.title}",
            ),
            {"famous_pun": 2.5},
            "with Dr. or Prof. before the name",
        ),
        Persona(
            "conspiracy_blogger",
            "Conspiracy blogger",
            "a conspiracy blogger who finally has the proof",
            (
                "the truth about the topic that they don't want you to know",
                "who is really behind the topic",
                "the evidence that the topic was never what it seemed",
            ),
            {
                "news": 3,
                "iceberg": 3,
                "org_chart": 2.5,
                "social_post": 2,
                "curve": 2,
                "venn_diagram": 1.5,
                "statement": 1.4,
                "reddit": 1.3,
                "quiz": 0.6,
                "inspiration": 0.6,
                "agenda": 0.5,
            },
            "one that promises to reveal what they don't want you to know",
            (
                "The Truth About {seed.title}",
                "What They Don't Want You to Know About {seed.title}",
                "Wake Up: Nothing About {seed.title} Is What You Think",
                "Who Really Controls {seed.title}?",
            ),
            {"fun_surname": 2, "pun": 1.5, "famous_pun": 0.7},
            "without Dr. or Prof.: a blogger needs no degree",
        ),
        Persona(
            "kindergarten_teacher",
            "Kindergarten teacher",
            "a kindergarten teacher who explains everything as to a class of five-year-olds",
            (
                "the topic as a lesson in sharing and being kind",
                "what the topic teaches us about growing up",
                "the topic, explained with the help of the class's favourite toys",
            ),
            {
                "quiz": 3,
                "gif": 1.6,
                "two_captions": 1.5,
                "full_image": 1.4,
                "three_captions": 1.3,
                "cycle": 1.3,
                "meme": 1.2,
                "questions": 1.5,
                "statement": 0.6,
                "chart": 0.5,
                "news": 0.5,
                "matrix_diagram": 0.4,
                "kpi": 0.3,
                "funnel": 0.3,
            },
            "one as simple and cheerful as a children's book",
            (
                "Let's Learn About {seed.title}!",
                "Making Friends with {seed.title}",
                "My First Book of {seed.title}",
                "Use Your Inside Voice: {seed.title}",
            ),
            {"pun": 2, "fun_surname": 2, "famous_pun": 0.7},
            "as the children call their teacher: Miss, Ms. or Mr. and a surname",
        ),
        Persona(
            "consultant",
            "Management consultant",
            "a management consultant who bills by the slide",
            (
                "a five-step framework for the topic",
                "the topic's synergies that nobody has leveraged yet",
                "a roadmap for the topic's next quarter",
            ),
            {
                "matrix_diagram": 3,
                "agenda": 2.5,
                "funnel": 2,
                "kpi": 2,
                "section": 2,
                "pyramid": 1.6,
                "venn_diagram": 1.5,
                "bar_chart": 1.4,
                "chart": 1.2,
                "full_image": 0.7,
                "history": 0.6,
                "gif": 0.5,
                "meme": 0.5,
                "anecdote": 0.5,
            },
            "like a consultancy's report: a framework, a roadmap or a strategy",
            (
                "A Strategic Framework for {seed.title}",
                "{seed.title}: A Roadmap to Synergy",
                "{seed.title}: A Maturity Model",
                "Leveraging {seed.title} for Growth",
            ),
            {"fun_surname": 2.5, "famous_pun": 0.6},
            "a corporate first name and surname, without Dr. or Prof.",
        ),
        Persona(
            "motivational_speaker",
            "Motivational speaker",
            "a motivational speaker who just lost a bet",
            (
                "how the topic changed the presenter's life",
                "mastering the topic in five steps",
                "the topic as a metaphor for life",
            ),
            {
                "inspiration": 3,
                "statement": 1.6,
                "deep": 1.5,
                "full_image": 1.4,
                "quote": 1.3,
                "pyramid": 1.3,
                "chart": 0.6,
                "news": 0.6,
                "org_chart": 0.5,
            },
            "like a self-help bestseller's promise",
            (
                "How {seed.title} Changed My Life",
                "Unleash the Power of {seed.title}",
                "Living Your Best Life with {seed.title}",
                "Say Yes to {seed.title}",
            ),
            {"pun": 2, "fun_surname": 1.5},
            "a name that fits on a poster, without Dr. or Prof.",
        ),
        Persona(
            "influencer",
            "Influencer",
            "an influencer with exactly 31 followers",
            (
                "the presenter's personal journey with the topic",
                "a challenge about the topic that went viral, among 31 people",
                "why everyone will be talking about the topic next year",
            ),
            {
                "social_post": 3,
                "meme": 2,
                "gif": 2,
                "full_image": 1.4,
                "quiz": 1.3,
                "timeline": 0.6,
                "chart": 0.6,
                "diagram": 0.6,
                "quote": 0.6,
                "history": 0.4,
            },
            "like clickbait for a video",
            (
                "I Tried {seed.title} for 30 Days",
                "{seed.title}: You Won't Believe What Happened Next",
                "Why Everyone Is Talking About {seed.title}",
                "{seed.title} Hacks Nobody Tells You About",
            ),
            {"pun": 2.5, "fun_surname": 1.5, "famous_pun": 0.7},
            "a name as catchy as a channel's, without Dr. or Prof.",
        ),
        Persona(
            "time_traveller",
            "Time traveller",
            "a time traveller trying not to give too much away",
            (
                "what the topic will become in the future",
                "the topic's history, as only an eyewitness could tell it",
                "the moment in history when everything about the topic changed",
            ),
            {
                "timeline": 3,
                "trend_chart": 2.2,
                "history": 2,
                "news": 1.6,
                "big_number": 1.3,
                "cycle": 1.3,
                "social_post": 0.7,
                "kpi": 0.5,
                "funnel": 0.5,
            },
            "one that lets slip a little too much about the future",
            (
                "{seed.title} in the Year 3000",
                "A Brief History of {seed.title}, From the Future",
                "What Really Happened to {seed.title}",
                "Trust Me, Keep an Eye on {seed.title}",
            ),
            {"famous_pun": 2.5, "pun": 1.2},
            "with Dr. before the name, a doctor of nothing in particular",
        ),
        Persona(
            "life_coach",
            "Life coach",
            "a life coach who is suspiciously calm",
            (
                "finding inner peace through the topic",
                "the topic as the path to the presenter's best self",
                "learning to let go of the topic",
            ),
            {
                "cycle": 3,
                "inspiration": 2,
                "pyramid": 2,
                "statement": 1.5,
                "quote": 1.4,
                "deep": 1.4,
                "full_image": 1.2,
                "chart": 0.7,
                "org_chart": 0.6,
                "news": 0.5,
                "kpi": 0.5,
            },
            "like a retreat's promise of inner peace",
            (
                "Finding Inner Peace Through {seed.title}",
                "{seed.title} and the Art of Letting Go",
                "Breathing Through {seed.title}",
                "Seven Habits I Learned from {seed.title}",
            ),
            {"pun": 2, "fun_surname": 1.5},
            "a soothing first name and surname, without Dr. or Prof.",
        ),
        Persona(
            "lighthouse_keeper",
            "Retired lighthouse keeper",
            "a retired lighthouse keeper with strong opinions",
            (
                "what forty years in a lighthouse taught the presenter about the topic",
                "why the topic was better in the old days",
                "a storm, a shipwreck and the topic",
            ),
            {
                "anecdote": 3,
                "history": 1.6,
                "full_image": 1.5,
                "statement": 1.4,
                "single_image": 1.3,
                "quote": 1.2,
                "meme": 0.6,
                "agenda": 0.5,
                "kpi": 0.3,
                "funnel": 0.3,
                "social_post": 0.3,
            },
            "like an old sailor's yarn",
            (
                "{seed.title}: What the Sea Taught Me",
                "Back in My Day, {seed.title} Meant Something",
                "Storms, Shipwrecks and {seed.title}",
                "A Lighthouse Keeper's Guide to {seed.title}",
            ),
            {"fun_surname": 2.5},
            "a weathered first name and surname, without Dr. or Prof.",
        ),
        Persona(
            "former_athlete",
            "Former athlete",
            "a former athlete turned philosopher",
            (
                "the topic as the toughest match of the presenter's career",
                "the training it takes to master the topic",
                "what winning and losing at the topic teach us about life",
            ),
            {
                "bar_chart": 2.5,
                "big_number": 2,
                "trend_chart": 1.5,
                "statement": 1.4,
                "kpi": 1.3,
                "quote": 1.3,
                "inspiration": 1.2,
                "gif": 1.2,
                "news": 0.8,
                "diagram": 0.7,
                "history": 0.7,
            },
            "like a locker-room speech that turns deep",
            (
                "{seed.title}: A Game of Inches",
                "The Inner Game of {seed.title}",
                "{seed.title}: No Pain, No Gain",
                "Going for Gold in {seed.title}",
            ),
            {"fun_surname": 2, "pun": 1.5},
            "a name a stadium would chant, without Dr. or Prof.",
        ),
        Persona(
            "passionate_expert",
            "Over-passionate expert",
            "a world-leading expert who is slightly too passionate about the topic",
            (
                "why everyone gets the topic wrong",
                "the economics of the topic that nobody talks about",
                "a love letter to the topic",
                "the dark side of the topic",
            ),
            {
                "anecdote": 1.5,
                "chart": 1.4,
                "big_number": 1.4,
                "quote": 1.2,
                "diagram": 1.2,
                "quiz": 1.2,
                "history": 1.2,
                "inspiration": 0.8,
            },
            "one that shows far too much passion for the topic",
            (
                "Everything I Know About {seed.title}, and Why It Matters",
                "{seed.title}: My Life's Work",
                "In Defence of {seed.title}",
                "Nobody Appreciates {seed.title} Enough",
            ),
            {"pun": 2, "famous_pun": 1.5},
            "with Dr. or Prof. before the name",
        ),
    )
}


def choices() -> tuple[str, ...]:
    """What generate_presentation's persona takes: random (the talk's dice pick one), none (no persona: the format's
    own talk), or a persona's name."""
    return (RANDOM, NONE, *PERSONAS)


def catalog() -> list[dict[str, str]]:
    """The personas, for a menu (or a site that shows a talk's): each with its name (what generate_presentation's
    persona takes), a label, and who presents (its voice)."""
    return [
        {"name": persona.name, "label": persona.label, "description": persona.voice} for persona in PERSONAS.values()
    ]


def persona(name: str) -> Persona:
    """The persona of that name (in any case). A ValueError for a persona there isn't."""
    found = PERSONAS.get(name.strip().lower())
    if found is None:
        raise ValueError(f"There's no persona {name!r}; there are {', '.join(choices())}")
    return found


def pick(chosen: str | None, rng: random_util.Rng) -> Persona | None:
    """The talk's persona: the one chosen, by name, or else (None, or random) one the talk's dice pick (rng: the talk's,
    whose "persona" stream picks it); none for "none". A ValueError for a persona there isn't."""
    wanted = chosen.strip().lower() if chosen is not None else RANDOM
    if wanted == NONE:
        return None
    if wanted == RANDOM:
        with random_util.use(rng.child("persona")):
            return random_util.choice(tuple(PERSONAS.values()))
    return persona(wanted)
