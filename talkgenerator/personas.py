"""Who presents a talk: its persona (docs/v5-plan.md, section 5.2).

The talk's dice pick a persona, such as a disgraced professor, a startup founder or a kindergarten teacher (or the
talk names one: generate_presentation's persona), which shapes more of the talk than how the language model writes:

- its voice, in which the model writes, and the kinds of talk it gives (its angles, of which the dice pick one); a
  persona may have pasts too, of which the dice pick one for the talk (a retiree's old job: see Persona.lived);
- how often each kind of slide comes up: multipliers on the format's own weights, by the slide generators' tags (see
  weight), so a medieval historian shows more history and timelines, and a startup founder more KPI tiles and funnels
  and less history. They never take a kind of slide away, and the format's caps still hold;
- the talk's title: a hint for the model on what the persona's titles are like, and title templates of its own for a
  classic talk, which half of the classic titles come from (see title_generator);
- the presenter's name (see nudge): weights over the name styles, by which the dice pick among the switched-on ones (a
  medieval historian's name is a famous-name pun more often), and for the model, how the presenter goes by (a
  professor with "Prof." before the name, a kindergarten teacher as the children call them). A talk that says which
  name styles it may have (name_styles) goes by those alone;
- the presenter's job on the title slide, for the model (job_hint: a founder is the founder and CEO of a startup);
- the talk's format, when the talk leaves it to its seed (schema "random", decision D61: see
  talkgenerator.schema.presentation_schema_types.pick_format): multipliers on the formats' weights, so a startup
  founder pitches and a disgraced professor gives academic talks far more often than the others do (in about two of
  every five of their talks; most of the rest are TED-like), while every other format keeps some chance with every
  persona.

Classic talks get the slides, the titles and the name styles; the voice and the angle are for a language model. The
persona comes from the talk's seed (its "persona" stream), before the format, the theme and the slides are picked, so
the same seed with the same answers gives the same talk. A talk may say which personas the seed picks from (see
allowed): a talk whose persona is among them keeps it, and the others get one of those. The deck and talk.started say
which persona a talk had (see record).

Across the personas, every kind of slide comes up about as often as the format's weights say (a test keeps their
average multiplier near 1): personas move a talk's slides around, rather than change the mix of all talks.

A talk without a persona (persona "none") is the format's own: its weights and titles, the default name styles as
they are, and no voice or angle for the model. With a classic theme, classic names and no model, that's the closest
to a talk of 2019.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
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

# Where a persona's past goes in its voice, angles and job hint (see Persona.lived)
PAST: Final = "{past}"

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
    # What the presenter's job on the title slide is, for the language model ("founder and CEO of their startup..."),
    # in place of the job field's example, which free models copied whoever presented
    job_hint: str
    # Multipliers on the theme families' weights, for a talk whose theme the seed picks (see
    # talkgenerator.design.themes.pick): a kindergarten teacher's talks are in the kids family more often
    themes: Mapping[str, float] = field(default_factory=dict)
    # Its favourite looks for some of the looks slides ask for, searched first, before the slide's own look (see
    # talkgenerator.images.context.ImageContext.tries): a medieval historian's weird pictures are weird medieval art
    looks: Mapping[str, str] = field(default_factory=dict)
    # Multipliers on the formats' weights, for a talk that leaves its format to its seed (schema "random": see
    # talkgenerator.schema.presentation_schema_types.FORMAT_WEIGHTS): a startup founder pitches far more often than the
    # others (1 for the formats it doesn't name)
    formats: Mapping[str, float] = field(default_factory=dict)
    # What the presenter may have been, of which the talk's dice pick one, for {past} in the voice, the angles and the
    # job hint (see lived): a retiree worked as a mail carrier, or as a lighthouse keeper. None for most personas.
    pasts: tuple[str, ...] = ()

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

    def lived(self, rng: random_util.Rng) -> Persona:
        """The persona as the talk has it (rng: the talk's): with the past its dice pick (its "persona", "past" stream,
        which no other choice uses) in the voice, the angles and the job hint. The same persona for one without pasts.
        A persona whose voice was always the same job made every talk of it about that job: a retired lighthouse
        keeper's two talks of the review set of 2026-11-08 had the lighthouse in their titles and on half of their
        slides."""
        if not self.pasts:
            return self
        with random_util.use(rng.child("persona", "past")):
            past = random_util.choice(self.pasts)
        return replace(
            self,
            voice=self.voice.replace(PAST, past),
            angles=tuple(angle.replace(PAST, past) for angle in self.angles),
            job_hint=self.job_hint.replace(PAST, past),
        )

    @property
    def description(self) -> str:
        """Who presents, for a menu: the voice, with a word for whichever past the dice pick."""
        return self.voice.replace(PAST, "the same odd job")

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
                "dare": 0.5,
                "wall_of_text": 2,
                "alignment_chart": 1.5,
                "red_flags": 0.5,
                "reviews": 0.5,
                "error_message": 1.5,
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
            "the chair they held before the scandal, in an absurdly specific field",
            themes={"academic": 5, "chalkboard": 3, "blueprint": 2, "kids": 0.3, "neon": 0.5},
            looks={"weird": "bad-charts", "neutral": "illustration"},
            formats={"academic": 15},
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
                "acronym": 2,
                "fun_fact": 0.5,
                "reviews": 2,
                "error_message": 1.3,
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
            "founder and CEO of their startup, with its made-up name",
            themes={"startup": 5, "Swiss poster": 2.5, "clean keynote": 2, "vintage paper": 0.3, "chalkboard": 0.5},
            looks={"photo": "corporate-stock", "neutral": "corporate-stock", "weird": "corporate-cringe"},
            formats={"pitch": 15, "keynote": 2},
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
                "acronym": 0.5,
                "alignment_chart": 2,
                "wall_of_text": 1.3,
                "reviews": 0.5,
                "error_message": 0.3,
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
            "a professorship in medieval studies, as grand and specific as it gets",
            themes={"vintage paper": 5, "newspaper": 2, "neon": 0.3, "hacker terminal": 0.3, "startup": 0.5},
            looks={"weird": "medieval", "neutral": "museum"},
            formats={"academic": 2, "pitch": 0.6},
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
                "flowchart": 3,
                "red_flags": 2.5,
                "error_message": 2,
                "wall_of_text": 1.5,
                "reviews": 0.6,
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
            "a title they gave themselves, as an independent researcher of something",
            themes={
                "hacker terminal": 5,
                "newspaper": 3,
                "1997 WordArt": 2,
                "90s desktop": 2,
                "corporate": 0.5,
                "clean keynote": 0.5,
            },
            looks={"weird": "pareidolia", "neutral": "liminal"},
            formats={"pitch": 0.6},
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
                "fun_fact": 2,
                "acronym": 0.5,
                "flowchart": 0.5,
                "wall_of_text": 0.3,
                "error_message": 0.5,
                "red_flags": 0.6,
                "reviews": 1.5,
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
            "their role at the kindergarten, made to sound grand",
            themes={"kids": 5, "chalkboard": 3, "Comic Sans everywhere": 2, "hacker terminal": 0.3, "brutalist": 0.3},
            looks={"weird": "wholesome", "neutral": "illustration"},
            formats={"pitch": 0.6, "academic": 0.6, "corporate": 0.5, "keynote": 0.7},
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
                "acronym": 3,
                "flowchart": 2,
                "dare": 0.5,
                "wall_of_text": 3,
                "red_flags": 0.6,
                "alignment_chart": 0.7,
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
            "a consultancy title, with Senior, Principal or Partner in it",
            themes={
                "corporate": 5,
                "sticky notes": 4,
                "clip-art corporate": 3,
                "Swiss poster": 2,
                "kids": 0.3,
                "chalkboard": 0.5,
            },
            looks={"photo": "corporate-stock", "neutral": "corporate-stock", "weird": "corporate-cringe"},
            formats={"pitch": 2, "corporate": 10},
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
                "acronym": 2,
                "reviews": 2.5,
                "red_flags": 1.5,
                "wall_of_text": 0.4,
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
            "a title like a self-help guru's",
            themes={"dark minimal": 3, "neon": 3, "1997 WordArt": 2, "academic": 0.5, "blueprint": 0.5},
            looks={"neutral": "places", "weird": "accidental-art"},
            formats={"pitch": 1.5, "keynote": 10},
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
                "dare": 3,
                "tier_list": 2.5,
                "alignment_chart": 2.5,
                "red_flags": 2,
                "reviews": 1.5,
                "wall_of_text": 0.3,
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
            "a title like an influencer's bio",
            themes={"neon": 4, "kids": 2, "Comic Sans everywhere": 2, "academic": 0.3, "newspaper": 0.5},
            looks={"weird": "memes", "neutral": "pictures"},
            formats={"pitch": 2, "academic": 0.6, "keynote": 2},
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
                "error_message": 3,
                "reviews": 1.3,
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
            "a job from a future they won't say much about",
            themes={"blueprint": 3, "neon": 3, "90s desktop": 3, "hacker terminal": 2, "corporate": 0.5},
            looks={"weird": "retro-futurism", "neutral": "space-science"},
            formats={"academic": 1.5, "keynote": 2},
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
                "tier_list": 0.5,
                "red_flags": 3,
                "error_message": 0.4,
                "wall_of_text": 0.5,
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
            "a title like a wellness guru's",
            themes={"clean keynote": 4, "sticky notes": 3, "dark minimal": 3, "brutalist": 0.3, "hacker terminal": 0.5},
            looks={"weird": "wholesome", "neutral": "places"},
            formats={"academic": 0.6, "keynote": 2, "corporate": 0.6},
        ),
        # (a retired lighthouse keeper until 2026-11-09, whose every talk was about the lighthouse: the user's "why not
        # retired person?" Its old job is one of its pasts now, which the dice pick)
        Persona(
            "retiree",
            "Retiree",
            "a retiree with strong opinions, who spent forty years working {past} (which comes up on a slide or two)",
            (
                "why the topic was better in the old days",
                "what forty years working {past} taught the presenter about the topic",
                "the topic, as the presenter's grandchildren tried to explain it to them",
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
                "flowchart": 0.5,
                "tier_list": 0.5,
                "error_message": 0.3,
                "wall_of_text": 0.5,
                "alignment_chart": 0.6,
                "reviews": 0.8,
            },
            "like an old-timer's yarn, about the topic rather than the old job (the title slide has that)",
            (
                "{seed.title}: What Forty Years Taught Me",
                "Back in My Day, {seed.title} Meant Something",
                "Kids These Days and {seed.title}",
                "An Old-Timer's Guide to {seed.title}",
            ),
            {"fun_surname": 2.5},
            "a weathered first name and surname, without Dr. or Prof.",
            "retired, after forty years working {past}",
            themes={"vintage paper": 4, "newspaper": 3, "neon": 0.3, "startup": 0.3},
            looks={"weird": "old-photos", "neutral": "places"},
            formats={"pitch": 0.6, "academic": 0.6, "corporate": 0.5, "keynote": 0.7},
            pasts=(
                "as a lighthouse keeper",
                "as a mail carrier",
                "as a zookeeper",
                "as a ferry captain",
                "as a school janitor",
                "as a piano tuner",
                "as a night guard",
                "as a bus driver",
                "as a museum guard",
                "as an ice-cream seller",
                "as a crossing guard",
                "as a forest ranger",
                "as a circus clown",
                "as a weather presenter",
                "as a submarine cook",
                "as a hotel concierge",
            ),
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
                "dare": 2,
                "tier_list": 2,
                "red_flags": 1.5,
                "alignment_chart": 1.3,
                "wall_of_text": 0.5,
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
            "the sport they played, and their new calling in philosophy",
            themes={"brutalist": 4, "Swiss poster": 4, "vintage paper": 0.5},
            looks={"weird": "accidental-art"},
            formats={"academic": 0.6, "keynote": 2, "corporate": 1.5},
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
                "fun_fact": 2,
                "alignment_chart": 1.5,
                "wall_of_text": 1.5,
                "red_flags": 0.8,
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
            "a professorship in an absurdly specific field",
            themes={"academic": 3, "chalkboard": 2, "dark minimal": 2, "clip-art corporate": 0.5},
            looks={"neutral": "museum"},
            formats={"academic": 2.5},
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
        {"name": persona.name, "label": persona.label, "description": persona.description}
        for persona in PERSONAS.values()
    ]


def persona(name: str) -> Persona:
    """The persona of that name (in any case). A ValueError for a persona there isn't."""
    found = PERSONAS.get(name.strip().lower())
    if found is None:
        raise ValueError(f"There's no persona {name!r}; there are {', '.join(choices())}")
    return found


def allowed(chosen: str | Iterable[str] | None = None) -> tuple[str, ...]:
    """The personas a talk's seed picks from (generate_presentation's personas), by their names (in any order and
    case), or one string with their names separated by commas ("startup_founder,consultant"): in the order of PERSONAS,
    so the order they're given in doesn't change a talk. None gives them all. A ValueError for a persona there isn't,
    for random or none among them (they go alone, as persona), and for none at all (persona "none" makes a talk
    without a persona)."""
    if chosen is None:
        return tuple(PERSONAS)
    parts = chosen.split(",") if isinstance(chosen, str) else list(chosen)
    wanted = {part.strip().lower() for part in parts if part.strip()}
    for name in sorted(wanted):  # (in a fixed order: the same names, the same error)
        if name in (RANDOM, NONE):
            raise ValueError(f"personas names the personas to pick from: {name!r} goes alone, as persona")
        if name not in PERSONAS:
            raise ValueError(f"There's no persona {name!r}; there are {', '.join(PERSONAS)}")
    if not wanted:
        raise ValueError("personas names at least one persona to pick from (persona 'none' has a talk without one)")
    return tuple(name for name in PERSONAS if name in wanted)


def pick(
    chosen: str | None,
    rng: random_util.Rng,
    weights: Mapping[str, float] | None = None,
    among: str | Iterable[str] | None = None,
) -> Persona | None:
    """The talk's persona: the one chosen, by name, or else (None, or random) one the talk's dice pick (rng: the talk's,
    whose "persona" stream picks it) among the personas it allows (among: see allowed; None, all of them); none for
    "none". A ValueError for a persona there isn't. (A persona chosen by name needn't be among them: it goes first, as a
    presenter's name goes before the name styles.)

    The dice pick each persona as likely as the others, or by weights (a talk format's: a startup founder pitches more
    often), by the personas' names (1 for those they don't name). They pick among all the personas first, and only
    when that one isn't allowed, again among those that are: so a talk whose persona is allowed keeps it, whichever
    others aren't, and each allowed persona comes up as often as the weights say among them."""
    wanted = chosen.strip().lower() if chosen is not None else RANDOM
    if wanted == NONE:
        return None
    if wanted != RANDOM:
        return persona(wanted).lived(rng)
    names = allowed(among)
    with random_util.use(rng.child("persona")):
        picked = _draw(tuple(PERSONAS.values()), weights)
        if picked.name not in names:
            picked = _draw(tuple(PERSONAS[name] for name in names), weights)
    return picked.lived(rng)


def _draw(pool: tuple[Persona, ...], weights: Mapping[str, float] | None) -> Persona:
    """One of the personas, as the current random stream picks it: each as likely, or by the weights."""
    if not weights:
        return random_util.choice(pool)
    return random_util.weighted_random([(weights.get(each.name, 1.0), each) for each in pool]) or pool[0]
