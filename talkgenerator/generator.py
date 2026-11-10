import argparse
import logging
import os
import pathlib
import queue
import subprocess
import sys
import threading
import warnings
from collections.abc import Callable, Iterable, Iterator
from typing import Any, Final

from pptx.presentation import Presentation

from talkgenerator import names, runtime_checker, settings, titles
from talkgenerator import personas as talk_personas
from talkgenerator.design import engine, themes
from talkgenerator.images import context as image_context
from talkgenerator.images import generation as image_generation
from talkgenerator.images import generators, licenses, vision
from talkgenerator.images.generation import ImageBudget
from talkgenerator.images.generators import ImageGenerator
from talkgenerator.llm.base import TextProvider
from talkgenerator.llm.ledger import Budget, Ledger, MeteredProvider
from talkgenerator.llm.providers import NoneProvider, from_settings, provider_from_spec
from talkgenerator.models.deck import Deck, DeckSlide
from talkgenerator.models.events import (
    SlideReady,
    SlideSpare,
    SlideStage,
    SlideUpdated,
    TalkEvent,
    TalkFinished,
    TalkProgress,
    TalkStage,
    TalkStarted,
)
from talkgenerator.models.theme import Theme
from talkgenerator.plan import languages, outline
from talkgenerator.schema import formats
from talkgenerator.schema.presentation_schema import Planning, Progress, TalkCancelled
from talkgenerator.schema.presentation_schema_types import RANDOM, get_schema, pick_format, schemas
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import word_frequency
from talkgenerator.util import image_util, os_util, random_util

DEFAULT_PRESENTATION_TOPIC = "cat"
DEFAULT_OUTPUT_FOLDER = "output"
MAX_PRESENTATION_SAVE_TRIES = 100

MIGRATING: Final = "https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md"
# What generate_presentation's DeprecationWarning says (talkgenerator.com's older /api/generate still calls it)
GENERATE_PRESENTATION_DEPRECATION: Final = (
    "generator.generate_presentation() is deprecated (it keeps working throughout talkgenerator 5). Use "
    "generator.stream_talk() instead: it takes the same talk options, and its talk.finished event has the deck, which "
    "talkgenerator.render.powerpoint.render_pptx(deck) turns into a PowerPoint. Or render a talk plan, written by "
    f"Claude or by you, with talkgenerator.plan.external.render_plan(). See {MIGRATING}"
)

logger = logging.getLogger("talkgenerator")


def generate_presentation_using_cli_arguments(args) -> tuple[Presentation | None, SlideDeck, str | None]:
    """Make a talk with the given topic."""
    if getattr(args, "print_logs", False):
        os_util.show_logs(logger, logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)

    runtime_checker.check_runtime_environment()

    # Print status details
    logger.info("******************************************")
    logger.info("Making {} slide talk on: {}".format(args.num_slides, args.topic))

    return _generate_presentation(
        schema=args.schema,
        slides=args.num_slides,
        topic=args.topic,
        title=args.title,
        topic_or_title=getattr(args, "topic_or_title", None),
        presenter=args.presenter,
        parallel=args.parallel,
        int_seed=args.int_seed,
        print_logs=False,  # already set up above
        save_ppt=args.save_ppt,
        output_folder=getattr(args, "output_folder", None) or DEFAULT_OUTPUT_FOLDER,
        open_ppt=args.open_ppt,
        debug_notes=getattr(args, "debug_notes", False),
        save_json=getattr(args, "save_json", False),
        llm=getattr(args, "llm", None),
        language=getattr(args, "language", None) or "en",
        theme=getattr(args, "theme", None),
        style_chaos=getattr(args, "style_chaos", 0.0) or 0.0,
        extreme_themes=getattr(args, "extreme_themes", True),
        theme_families=getattr(args, "theme_families", None),
        name_styles=getattr(args, "name_styles", None),
        license_policy=getattr(args, "license_policy", None),
        image_generator=getattr(args, "image_generator", None),
        image_budget=_image_budget(getattr(args, "generated_images", None)),
        persona=getattr(args, "persona", None),
        personas=getattr(args, "personas", None),
        vision_pick=getattr(args, "vision_pick", None),
        llm_level=getattr(args, "llm_level", None),
    )


def _image_budget(generated_images: int | None) -> ImageBudget | None:
    """The image budget of --generated_images (with TALKGENERATOR_IMAGE_COST_LIMIT's dollars), or None: the settings'."""
    if generated_images is None:
        return None
    return ImageBudget(max_images=max(0, generated_images), max_cost_usd=settings.image_cost_limit())


def generate_presentation(
    schema: str,
    slides: int,
    topic: str | list[str] | None = None,
    title: str | None = None,
    presenter: str | None = None,
    parallel: bool | int = True,
    int_seed: int | None = None,
    save_ppt: bool = True,
    output_folder: str = DEFAULT_OUTPUT_FOLDER,
    open_ppt: bool = False,
    print_logs=False,
    debug_notes: bool = False,
    save_json: bool = False,
    llm: TextProvider | str | None = None,
    language: str = "en",
    budget: Budget | None = None,
    theme: str | None = None,
    style_chaos: float = 0.0,
    extreme_themes: bool = True,
    progress: Progress | None = None,
    name_styles: str | Iterable[str] | None = None,
    topic_or_title: str | None = None,
    license_policy: str | Iterable[str] | None = None,
    image_generator: ImageGenerator | str | None = None,
    image_budget: ImageBudget | None = None,
    persona: str | None = None,
    personas: str | Iterable[str] | None = None,
    vision_pick: bool | str | TextProvider | None = None,
    theme_families: str | Iterable[str] | None = None,
    llm_level: str | None = None,
) -> tuple[Presentation | None, SlideDeck, str | None]:
    """Deprecated, for talkgenerator 4's callers: generate a talk, save it as a PowerPoint in output_folder (unless
    save_ppt is off), and return the PowerPoint, the talk and the file it went to (see _generate_presentation for the
    options).

    It keeps working throughout talkgenerator 5, with a DeprecationWarning that says what to use instead: stream_talk,
    which takes the same talk options, and whose talk.finished event has the deck, which
    talkgenerator.render.powerpoint.render_pptx turns into a PowerPoint; or a talk plan, rendered with
    talkgenerator.plan.external.render_plan (docs/migrating-from-4.md). talkgenerator's own commands (the command
    line, the MCP server, the checks) and stream_talk make their talks with _generate_presentation, so they don't
    warn."""
    warnings.warn(GENERATE_PRESENTATION_DEPRECATION, DeprecationWarning, stacklevel=2)
    return _generate_presentation(
        schema,
        slides,
        topic=topic,
        title=title,
        presenter=presenter,
        parallel=parallel,
        int_seed=int_seed,
        save_ppt=save_ppt,
        output_folder=output_folder,
        open_ppt=open_ppt,
        print_logs=print_logs,
        debug_notes=debug_notes,
        save_json=save_json,
        llm=llm,
        language=language,
        budget=budget,
        theme=theme,
        style_chaos=style_chaos,
        extreme_themes=extreme_themes,
        progress=progress,
        name_styles=name_styles,
        topic_or_title=topic_or_title,
        license_policy=license_policy,
        image_generator=image_generator,
        image_budget=image_budget,
        persona=persona,
        personas=personas,
        vision_pick=vision_pick,
        theme_families=theme_families,
        llm_level=llm_level,
    )


def _generate_presentation(
    schema: str,
    slides: int,
    topic: str | list[str] | None = None,
    title: str | None = None,
    presenter: str | None = None,
    parallel: bool | int = True,
    int_seed: int | None = None,
    save_ppt: bool = True,
    output_folder: str = DEFAULT_OUTPUT_FOLDER,
    open_ppt: bool = False,
    print_logs=False,
    debug_notes: bool = False,
    save_json: bool = False,
    llm: TextProvider | str | None = None,
    language: str = "en",
    budget: Budget | None = None,
    theme: str | None = None,
    style_chaos: float = 0.0,
    extreme_themes: bool = True,
    progress: Progress | None = None,
    name_styles: str | Iterable[str] | None = None,
    topic_or_title: str | None = None,
    license_policy: str | Iterable[str] | None = None,
    image_generator: ImageGenerator | str | None = None,
    image_budget: ImageBudget | None = None,
    persona: str | None = None,
    personas: str | Iterable[str] | None = None,
    vision_pick: bool | str | TextProvider | None = None,
    theme_families: str | Iterable[str] | None = None,
    llm_level: str | None = None,
) -> tuple[Presentation | None, SlideDeck, str | None]:
    """Generate a talk, as talkgenerator's own commands and stream_talk do: what generate_presentation does, without
    its DeprecationWarning. With debug_notes, every slide's speaker notes explain how it was generated.

    schema is the talk's format, the name of a presentation schema: "default" (a TED-like talk), "ted" (the TED-like
    talk with copyright-free images only), "pitch", "academic" and the others of talkgenerator.plan.external.FORMATS;
    or "random", for one the talk's seed picks after its persona, who favours some (a startup founder pitches more often, a
    disgraced professor gives academic talks), among the TED-like talk and the formats beyond it (see
    talkgenerator.schema.presentation_schema_types.pick_format). Copyright-free images go with any format: ask for
    them with license_policy "open". The deck says which format the talk had (schema_name).

    topic is what the talk is about (or topics, separated by commas), and title its title; without a title, it gets
    one. topic_or_title stands for both, when what's given could be either, as what someone types can be: "penguins",
    "Cats are liquid" or "Why I Joined a Penguin Cult". What's in quote marks is the title, word for word. What's
    clearly a title (four words or more, or a question or an exclamation) stays the talk's title, with only its obvious
    slips fixed; anything shorter is the topic (or a premise), on which the language model that writes the talk builds
    a funnier, more specific title, in the same request. Without a language model, talkgenerator guesses: a title when it's clearly one, starts like one ("How
    to", "Why", "The", "A", "My") or makes a claim ("Cats are liquid"), which stays as typed. The deck tells how it was
    read (see talkgenerator.titles). It's given instead of topic and title, never with them.

    With save_json, the talk is also saved as a deck (see talkgenerator.models.deck): as JSON, next to the PowerPoint
    and with the same name, or on its own in output_folder when save_ppt is off. slide_deck.to_deck() gives the same
    deck as an object.

    llm is the language model that writes the talk: a provider, a spec such as "anthropic:claude-opus-5-5", or None
    for the one TALKGENERATOR_LLM sets (without one, talks are classic). It writes in the given language, and the
    budget limits what it may cost; the deck tells what it used.

    llm_level is how much the language model does (see talkgenerator.plan.outline): "basic", one request a talk, in
    which it writes every slide from the word the talk's dice give it; or "advanced", as it first plans the talk (its
    thesis, a running gag, and every slide's word, among those the dice offer, or one of its own, and its idea: the
    point it makes, what a chart measures or a diagram compares), and writes every slide in a request of its own as
    soon as its idea is in, in parallel. None is the one TALKGENERATOR_LLM_LEVEL names, or else advanced on a model of
    your own that costs (Claude, OpenAI's, your ChatGPT plan's, OpenRouter's paid ones) and basic on the free ones.
    Classic talks have none; the deck says which level its slides were written at (llm_level: advanced only when the
    plan came in).

    theme is "random" (a theme of a family the seed picks, extremes such as 1997 WordArt too unless extreme_themes
    is off), "classic" (the 2019 template), a family's name such as "dark minimal", or "chaos" (every slide in a
    theme of its own): one of talkgenerator.design.themes.choices(), which catalog() describes. None is the one
    TALKGENERATOR_THEME names, or else random. style_chaos is how many slides get a theme of their own (0 to 1).

    theme_families are the families a random theme can be of (the talk's, and a chaos deck's slides' own): their
    names, as a list or one string separated by commas, such as "dark minimal,Swiss poster" (see
    talkgenerator.design.themes.allowed). None: all of them (the extremes too, unless extreme_themes is off). A talk
    whose seed picks a family among them keeps its theme, whichever others are left out; the others get a theme of
    one of those, each as often as its weight and the persona's favourites say among them (decision D62). A family
    named as the theme goes first, as a persona named goes before personas.

    presenter is the presenter's name, which never goes to a language model. Without one, a name is made up in one of
    name_styles, which the talk's seed picks: "pun" (such as Prof. Anna Tomy, for a talk on medicine),
    "fun_surname" (Linda Hivesworth, for bees), "famous_pun" (Albert Einstone, for geology) and "classic" (a random
    first and last name, as in 2019), as a list or one string separated by commas (see talkgenerator.names.catalog).
    The language model that writes the talk writes the name too, in the same request; without one (or when its name
    won't do), talkgenerator has names of its own for some topics, and makes up a classic name otherwise. None: the
    first three, the talk's persona favouring some (a medieval historian's name is a famous-name pun more often); none
    at all: classic names only.

    persona is who presents the talk (see talkgenerator.personas.catalog): a name such as "startup_founder" or
    "kindergarten_teacher", None (or "random") for one the talk's seed picks, or "none" for none, which makes the
    format's own talk. They shape the talk: which kinds of slides it favours (a startup founder's KPI tiles and
    funnels), its title (their kind of title, from the language model, or in a classic talk half the time one of their
    own templates), the style of the presenter's name (unless name_styles says), the voice and angle the language
    model writes in, the theme's family when the theme is random (a kindergarten teacher's talks are in the kids
    family more often), the looks some of its pictures are searched in first (a medieval historian's weird pictures
    are weird medieval art), and the format when the schema is random. The deck says which persona it had.

    personas are the personas the talk's seed picks from (when persona is None or "random"): their names, as a list or
    one string separated by commas (see talkgenerator.personas.allowed). None: all of them. A talk whose seed picks a
    persona among them keeps it, whichever others are left out; the others get one of those. A persona named (or
    "none") goes first, as a presenter's name goes before name_styles.

    license_policy is the license classes the talk's images may have (see talkgenerator.images.licenses): "all", "open"
    (everything but fair use: no memes, gifs or Reddit's posts, for decks shown in public), or the classes, as a list
    or separated by commas ("public-domain,open"). None is the format's: "open" for ted, else "all".

    image_generator generates pictures for the slides stock photos can't show well (the presenter's weird hobby, the
    cover of the book they wrote, an old photo of a moment in the made-up history of something), and for a slide whose
    images can't be found: a generator (see talkgenerator.images.generators), a spec such as "openai:gpt-image-2", or
    None for the one TALKGENERATOR_IMAGE_GENERATOR names (without one, nothing is generated: a key alone never makes a
    talk generate). Only slides a language model writes (or a plan) get them, as their texts say what a picture is to
    show; their pictures are generated while the talk is made, a few at most (image_budget: by default 3, and no
    dollar limit), at the cost of the generator's owner, which the deck's usage says. See
    talkgenerator.images.generation.

    vision_pick has a vision model look at a few candidates for every picture of the slides a language model writes,
    side by side on one contact sheet, and pick the one that shows what the slide asked for (or none: the finder's
    picture then stays), in one request a talk, once the last slide is settled: True for the talk's own model when it
    reads pictures (Claude, OpenAI), else OpenRouter's free models that do (they need an OpenRouter key, and cost
    nothing but a request of the free tier's); or a model's spec, such as "anthropic:claude-haiku-5-5", or a
    provider. Off by default (None, False or "none"). The picks are in the deck (each picture's `vision`), its usage
    counts the request, and the talk's budget holds it too. See talkgenerator.images.vision.

    parallel makes the slides at the same time (searching their images takes most of the time): True, all of them (a
    language model's eight at a time); a number, at most that many at once (a small server's few: each slide being
    made holds what it found until it's settled); False, one by one. The talk comes out the same either way.

    progress follows the talk while it's made (see stream_talk, which hands it over in events)."""
    theme = theme or settings.theme()
    if theme not in themes.choices():
        raise ValueError(f"There's no theme {theme!r}; there are {', '.join(themes.choices())}")
    # (a ValueError for a family there isn't, or for only extremes with the extremes left out)
    families = themes.families(extreme_themes, theme_families) if theme_families is not None else None
    chosen_styles = names.styles(name_styles)  # (a ValueError for a style there isn't)
    languages.language(language)  # (a ValueError for a language talkgenerator doesn't know)
    outline.check(llm_level)  # (a ValueError for a level there isn't)
    if topic_or_title is not None and (topic or title):
        raise ValueError("topic_or_title stands for both the topic and the title: give it without them")
    # (on one line, but with its quote marks, if any: they make it a title, word for word)
    typed = " ".join(topic_or_title.split()) if topic_or_title and titles.normalised(topic_or_title) else None
    named = get_schema(schema) if schema != RANDOM else None  # (a KeyError for a schema there isn't)
    allowed = talk_personas.allowed(personas)  # (a ValueError for a persona there isn't)
    if license_policy is not None:
        licenses.policy(license_policy)  # (a ValueError for a policy there isn't)
    if print_logs:
        os_util.show_logs(logger)
    logger.info("**************************")
    logger.info("Generating presentation...")
    # Without some API keys, fewer image sources are used: say so (once), as it explains a lot about the results
    settings.report_missing_keys()

    # The talk's random choices all come from its seed (a random one if none is given), see random_util
    rng = random_util.Rng(int_seed)
    logger.info("Presentation seed: {} (pass it as int_seed to make this talk again)".format(rng.root_seed))

    # Who presents it: a persona its seed picks among those it allows (a format beyond the TED-like talks it asks for
    # has its favourites: a startup founder pitches more often), unless it names one, or none (see
    # talkgenerator.personas)
    asked_format = named.format if named is not None else None
    chosen_persona = talk_personas.pick(
        persona, rng, asked_format.personas if asked_format is not None else None, allowed
    )
    picked = persona is None or persona.strip().lower() == talk_personas.RANDOM
    among = f", one of the {len(allowed)} it allows" if picked and len(allowed) < len(talk_personas.PERSONAS) else ""
    if chosen_persona is not None:
        logger.info("Persona: {} ({}){}".format(chosen_persona.label, chosen_persona.voice, among))
    else:
        logger.info("Persona: none (the format's own talk)")

    # Its format: the one it asks for, or one its seed picks, which its persona favours (a startup founder pitches
    # more often: see talkgenerator.schema.presentation_schema_types.pick_format)
    schema = pick_format(schema, rng, chosen_persona)
    if named is None:
        logger.info("Format: {} (the talk's seed picked it, as its persona favours)".format(schema))
    presentation_schema = named if named is not None else get_schema(schema)
    talk_format = presentation_schema.format
    policy = licenses.policy(license_policy if license_policy is not None else presentation_schema.license_policy)

    # The talk's theme, from its seed too, of a family its persona and its format favour more often, among those it
    # allows (see talkgenerator.design.themes)
    if theme == themes.CHAOS:
        theme, style_chaos = themes.RANDOM, 1.0
    favoured = formats.multiplied(
        chosen_persona.themes if chosen_persona is not None else None,
        talk_format.themes if talk_format is not None else None,
    )
    chosen_theme = themes.pick(theme, rng.child("theme"), extreme_themes, favoured, families)
    if chosen_theme is not None:
        allows = ""
        if theme == themes.RANDOM and families is not None and families != themes.families(extreme_themes):
            allows = f", of one of the {len(families)} families it allows"
        logger.info("Theme: {}{}".format(chosen_theme.name, allows))

    logger.info("Presentation schema: {}".format(presentation_schema))
    logger.info("License policy: {} ({})".format(policy.name, ", ".join(sorted(policy.classes))))

    if typed:  # (its topics, before a language model reads it: by talkgenerator's guess)
        topic = titles.topics_from(typed, language)
    if not topic:
        topic = (word_frequency.get_rarest_word(title) if title else None) or DEFAULT_PRESENTATION_TOPIC

    # Extract topics from given (possibly comma separated) topic
    if isinstance(topic, (list, tuple)):
        topics = list(topic)
    else:
        topics = [part.strip() for part in topic.split(",")]

    logger.info("Presentation topics: {}".format(topics))
    logger.info("Presentation num_slides: {}".format(slides))
    logger.info(
        "Presentation presenter: {}".format(presenter or "made up ({})".format(", ".join(chosen_styles) or "classic"))
    )
    logger.info("Presentation title: {}".format(title))
    if typed:
        logger.info("Presentation topic or title: {}".format(typed))
    logger.info("Presentation parallel: {}".format(parallel))
    logger.info("Presentation int_seed: {}".format(int_seed))
    logger.info("Presentation save_ppt: {}".format(save_ppt))

    # The language model that writes the talk, if any; every request it gets is written down in the talk's ledger
    provider = _language_model(llm)
    ledger = Ledger()
    # How much it does: as asked, or TALKGENERATOR_LLM_LEVEL says, or else Advanced on a model of your own that costs
    level = outline.level(llm_level, provider)
    if provider is not None:
        logger.info("Language model: {} ({} level)".format(provider.id, level))
    elif language != "en":
        logger.warning("Talks in other languages than English need a language model: this one is in English")

    # The pictures it may generate (with a generator it's given, or the settings'), counted in the same ledger: for the
    # slides a language model writes, whose texts say what a picture is to show
    generation = image_generation.for_talk(image_generator, image_budget, policy, ledger, topics, presenter)
    if generation is not None and provider is None:
        logger.info("Classic talks generate no pictures: {} isn't asked".format(generation.generator.id))
        generation = None
    if generation is not None:
        logger.info(
            "Image generator: {} (this talk may generate {})".format(generation.generator.id, generation.estimate())
        )

    # A vision model that picks its pictures among their candidates, if it's asked for: for the slides a language
    # model writes, whose image queries say what a picture is to show, in one request once they're settled
    picking = vision.for_talk(vision_pick, provider, ledger, budget, rng.child("vision pick"), presenter)
    if picking is not None:
        logger.info("Vision pick: {}".format(picking.id))

    # Generate the presentation object, finding its images by its license policy, theme and format
    # (with the persona's favourite looks, searched first for the looks they have one for)
    persona_looks = chosen_persona.looks if chosen_persona is not None else {}
    images = image_context.ImageContext(
        policy,
        palette(chosen_theme),
        presentation_schema.looks,
        generation,
        persona_looks=persona_looks,
        vision=picking,
    )
    with image_context.for_talk(images):
        presentation, slide_deck = presentation_schema.generate_presentation(
            topics=topics,
            num_slides=slides,
            presenter=presenter,
            title=title,
            parallel=parallel,
            int_seed=int_seed,
            save_ppt=save_ppt,
            debug_notes=debug_notes,
            rng=rng,
            llm=MeteredProvider(provider, ledger, budget or Budget()) if provider is not None else None,
            language=language,
            theme=chosen_theme,
            style_chaos=style_chaos,
            extreme_themes=extreme_themes,
            theme_families=families,
            progress=progress,
            # (None: the default styles, as the persona nudges them; styles given go alone)
            name_styles=chosen_styles if name_styles is not None else None,
            topic_or_title=typed,
            persona=chosen_persona,
            llm_level=level,
        )
    slide_deck.schema_name = schema  # (the format it asked for, or the one its seed picked)
    slide_deck.license_policy = policy.name
    slide_deck.usage = ledger.total()
    answered = ledger.language_models()
    if slide_deck.language_model is not None and answered:
        slide_deck.language_model = answered[-1]  # (the model that answered, which a router picks)
    picked_by = ledger.vision_models()
    slide_deck.vision_model = picked_by[-1] if picked_by else None
    if provider is not None or generation is not None:
        logger.info(ledger.summary())

    logger.info("**************************")
    logger.info("Presentation generated: {}".format(presentation))
    logger.info("Slide deck generated: {}".format(slide_deck))

    cleaned_topics = ",".join(topics).replace(" ", "").replace(",", "_")
    file_name = "".join(e for e in cleaned_topics if e.isalnum() or e == "_")

    logger.info("Slide deck structured data: {}".format(slide_deck.get_structured_data()))

    # Save presentation
    presentation_file = None
    if save_ppt:
        presentation_file = save_presentation_to_pptx(output_folder, file_name, presentation)

    if save_json:
        save_deck_to_json(slide_deck.to_deck(), output_folder, file_name, next_to=presentation_file)

    # Open the presentation
    if save_ppt and open_ppt and presentation_file is not None:
        path = os.path.realpath(presentation_file)
        _open_file(path)

    return presentation, slide_deck, presentation_file


def stream_talk(
    schema: str,
    slides: int,
    topic: str | list[str] | None = None,
    title: str | None = None,
    presenter: str | None = None,
    parallel: bool | int = True,
    int_seed: int | None = None,
    llm: TextProvider | str | None = None,
    language: str = "en",
    budget: Budget | None = None,
    theme: str | None = None,
    style_chaos: float = 0.0,
    extreme_themes: bool = True,
    name_styles: str | Iterable[str] | None = None,
    topic_or_title: str | None = None,
    license_policy: str | Iterable[str] | None = None,
    image_generator: ImageGenerator | str | None = None,
    image_budget: ImageBudget | None = None,
    persona: str | None = None,
    personas: str | Iterable[str] | None = None,
    vision_pick: bool | str | TextProvider | None = None,
    theme_families: str | Iterable[str] | None = None,
    spares: int = 0,
    slide_seconds: float | None = None,
    llm_level: str | None = None,
    progress: bool = False,
) -> Iterator[TalkEvent]:
    """Make a talk as generate_presentation does (the same deck, for the same options, seed and answers), handing
    over what's ready while it's made (see talkgenerator.models.events): talk.started once its title is known (the
    one it settles on, and for a topic_or_title, how that was read), a slide.ready for every slide as soon as it's
    settled, in order and laid out in the talk's theme, and talk.finished with the whole deck. Meanwhile, the slides
    after it are being made: a language model's while it writes them.

    With spares, it also makes that many spare slides, for a presenter who goes on before the next slide is in: as
    soon as the talk has started, on a thread of their own, each a slide that takes a fraction of a second and hardly
    ever fails (a quiz, a tier list, red flags, an acronym... from the TED pack's templates, without pictures), about
    the talk's topic, as the talk's persona favours them; in a talk in another language than English, whose classic
    slides would be English, a picture of the topic without text. Each comes as a slide.spare once it's made, laid
    out in the talk's theme without a slide number, until the talk's slides are all in: a spare that isn't made by
    then is left out. Spares are none of the talk's slides: the deck (and so its PowerPoint) leaves them out, and as
    they have random streams of their own, the talk's slides come out the same with spares or without. A spare can't
    be made for a talk on a topic its slides wouldn't make light of (see talkgenerator.sources.slide_texts.sensitive).

    With slide_seconds, every slide but the title slide has that long, at most, from when it could come (once the
    slide before it came, and its text, for a slide a language model writes): one that isn't made by then (its pictures
    still being looked for, say) comes at once with what's quick instead. A slide the model wrote keeps its texts: it
    comes without the pictures it can do without, and with spare pictures of the talk's topic, found early, for the
    ones it can't. Else a stand-in takes its place, a slide of the spare slides' kinds about the slide's own seed, made
    in a hundredth of a second (in a talk in another language, a spare picture of the topic, without text). What the
    slide waited for goes on by itself, and once it's done, the real slide comes after all, in place of what stood in
    for it (a slide.updated at its index, that's late: laid out in its place, the slides after it as they were), in the
    deck and its PowerPoint too, unless it repeats another slide or the talk has as many slides of its kind as it may
    have. Once the other slides are in, talk.finished waits for it 20 seconds at most (presentation_schema.LATE_SECONDS); after that, what
    stood in for it is the talk's slide. Off by default (None): the same seed gives the same talk as long as no slide
    runs out of time, as it then depends on how long the sources take.

    In a talk that generates pictures (image_generator: see generate_presentation), a slide comes with its stock photo
    where a generated picture is to go, and comes again (slide.updated, at the same index, laid out the same way) once
    that's in; talk.finished comes once all of them are in. In a talk with a vision pick (vision_pick: see
    generate_presentation), the slides come with the finder's pictures as soon as they're settled, as without one, and a
    slide whose picture the vision model picked another one for comes again (slide.updated) once the last slide is
    settled and the model has answered; talk.finished comes after that.

    With progress, it also hands over how far the talk is (talk.progress: see talkgenerator.models.events.TalkProgress),
    from its very start, before talk.started, and whenever that changes until talk.finished: where the talk is
    (starting, asking its language model, planning, writing, composing, finishing), where each of its slides is
    (waiting, planned, written, ready), how much of the model's plan came in, and how many of its slides the model
    wrote, so that whoever shows the talk can show how far it is, as a free model can take a while to answer. Off by
    default: then the events are the ones above, and only those.

    Images are probed rather than downloaded (see talkgenerator.util.image_util.probing): a browser that shows the
    slides loads them itself. Nothing is saved: the deck in talk.finished renders as a PowerPoint
    (talkgenerator.render.powerpoint.render_pptx), which downloads them then.
    Stopping the iteration (closing the iterator, or leaving a for loop over it) stops the talk, and an error that
    stopped it comes out of the iterator."""
    events: queue.SimpleQueue[TalkEvent | None] = queue.SimpleQueue()  # (None: the end)
    following = _Following(
        events.put, spares=max(0, spares), slide_seconds=slide_seconds, stages=slides if progress else None
    )
    failures: list[BaseException] = []

    def make() -> None:
        try:
            following.begin()
            with image_util.probing():
                _, slide_deck, _ = _generate_presentation(
                    schema,
                    slides,
                    topic=topic,
                    title=title,
                    presenter=presenter,
                    parallel=parallel,
                    int_seed=int_seed,
                    save_ppt=False,
                    llm=llm,
                    language=language,
                    budget=budget,
                    theme=theme,
                    style_chaos=style_chaos,
                    extreme_themes=extreme_themes,
                    progress=following,
                    name_styles=name_styles,
                    topic_or_title=topic_or_title,
                    license_policy=license_policy,
                    image_generator=image_generator,
                    image_budget=image_budget,
                    persona=persona,
                    personas=personas,
                    vision_pick=vision_pick,
                    theme_families=theme_families,
                    llm_level=llm_level,
                )
                events.put(TalkFinished(deck=following.finished(slide_deck.to_deck())))
        except TalkCancelled:
            pass
        except BaseException as error:  # (for whoever iterates)
            failures.append(error)
        finally:
            events.put(None)

    threading.Thread(target=make, name="talk", daemon=True).start()
    try:
        while (event := events.get()) is not None:
            yield event
    finally:
        following.cancelled.set()  # (stops the talk, if it isn't done)
    if failures:
        raise failures[0]


class _Following:
    """Turns a talk's progress into events (see stream_talk), and stops the talk once they're not wanted anymore. It
    wants that many spare slides, and gives every slide that long at most (spares and slide_seconds: see
    talkgenerator.schema.presentation_schema.Progress). With stages, the number of the talk's slides, it hands over
    how far the talk is too (talk.progress events: see _Stages), and wants to know how far its language model is
    (planning)."""

    def __init__(
        self,
        hand_over: Callable[[TalkEvent], None],
        spares: int = 0,
        slide_seconds: float | None = None,
        stages: int | None = None,
    ) -> None:
        self.hand_over = hand_over
        self.spares = spares
        self.slide_seconds = slide_seconds
        self.cancelled = threading.Event()
        self._layout: engine.DeckLayout | None = None
        self._handed_over = 0
        self._indices: dict[int, int] = {}  # every handed-over slide's index, by its slide number
        self._shown: dict[int, DeckSlide] = {}  # every handed-over slide by its index, as it was last handed over
        self._replaced = False  # whether a slide came after all, in place of what stood in for it (see replaced)
        # (a slide is laid out again, and handed over again, while later ones are being handed over)
        self._lock = threading.RLock()
        self._stages = _Stages(hand_over, stages, self.cancelled) if stages is not None else None
        # (what the talk tells of its language model, when its stages are wanted: none otherwise, so it tells nothing)
        self.planning: Callable[[Planning], None] | None = self._stages.planning if self._stages is not None else None

    def begin(self) -> None:
        """The talk is starting: its first talk.progress, if its stages are wanted."""
        if self._stages is not None:
            self._stages.begin()

    def started(self, slide_deck: SlideDeck) -> None:
        self._go_on()
        theme = slide_deck.theme
        if theme is not None:  # (laid out one by one as they come, as to_deck lays them all out, "7/12" by the size)
            self._layout = engine.DeckLayout(
                slide_deck.seed,
                theme,
                slide_deck.style_chaos,
                slide_deck.extreme_themes,
                slide_deck.theme_families,
                total=slide_deck.size,
            )
        self.hand_over(
            TalkStarted(
                title=slide_deck.title,
                presenter=slide_deck.presenter,
                persona=slide_deck.persona,
                topics=slide_deck.topics,
                topic_or_title=slide_deck.topic_or_title,
                language=slide_deck.language,
                seed=slide_deck.seed,
                slides=slide_deck.size,
                theme=theme.name if theme is not None else "classic",
                style=theme,
                language_model=slide_deck.language_model,
            )
        )
        if self._stages is not None:
            self._stages.started()

    def settled(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
        self._go_on()
        with self._lock:
            deck_slide = slide.to_deck_slide()
            if self._layout is not None:
                deck_slide = self._layout.next(deck_slide)
            index = self._indices[slide_nr] = self._handed_over
            self._shown[index] = deck_slide
            self.hand_over(SlideReady(index=index, slide=deck_slide))
            self._handed_over += 1
        if self._stages is not None:
            self._stages.ready(slide_nr)
        # A slide shown is a slide used, which some sources want to hear of (a download, at Unsplash), as a PowerPoint
        # tells them when it gets the slide. (A PowerPoint made later from the deck doesn't tell them again.)
        for image in slide.image_store().values():
            image.mark_used()

    def updated(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
        """A slide handed over before has changed (a generated picture in its stock photo's place, or a vision pick in
        the finder's): hand it over again, at its index, laid out as it was."""
        if self.cancelled.is_set():
            return
        with self._lock:
            index = self._indices.get(slide_nr)
            if index is None:
                return
            deck_slide = slide.to_deck_slide()
            if self._layout is not None:
                deck_slide = self._layout.again(index, deck_slide)
            self._shown[index] = deck_slide
            self.hand_over(SlideUpdated(index=index, slide=deck_slide))
        for image in slide.image_store().values():  # (a picture shown is a picture used, as in settled)
            image.mark_used()

    def replaced(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
        """A slide that ran out of time, come after all, in place of what stood in for it (see
        talkgenerator.schema.presentation_schema._LateSlides): hand it over at the stand-in's index, as a slide.updated
        that's late, laid out in the stand-in's place (as engine.DeckLayout.again lays a slide out: the slides after it
        stay as they were laid out)."""
        if self.cancelled.is_set():
            return
        with self._lock:
            index = self._indices.get(slide_nr)
            if index is None:
                return
            deck_slide = slide.to_deck_slide()
            if self._layout is not None:
                deck_slide = self._layout.again(index, deck_slide)
            self._shown[index] = deck_slide
            self._replaced = True
            self.hand_over(SlideUpdated(index=index, slide=deck_slide, late=True))
        for image in slide.image_store().values():  # (a picture shown is a picture used, as in settled)
            image.mark_used()

    def finished(self, deck: Deck) -> Deck:
        """The finished deck, for talk.finished: as the talk's deck is (deck), but once a slide came after all in place
        of what stood in for it, with its slides as they were handed over, laid out as they were shown (laying the
        deck out at once would lay the slides after it out anew, after another slide than they came after)."""
        with self._lock:
            if not self._replaced or sorted(self._shown) != list(range(len(deck.slides))):
                return deck
            return deck.model_copy(update={"slides": tuple(self._shown[index] for index in range(len(deck.slides)))})

    def spare(self, slide_deck: SlideDeck, number: int, slide: Any) -> None:
        """A spare slide (the number-th, from 0), made: hand it over, laid out in the talk's theme as its slides are,
        but without a slide number, and without changing how they're laid out (see engine.DeckLayout.spare). Its
        pictures, if any, aren't marked used: a spare is only shown when a presenter catches up with the making."""
        if self.cancelled.is_set():
            return
        deck_slide = slide.to_deck_slide()
        if self._layout is not None:
            deck_slide = self._layout.spare(number, deck_slide)
        self.hand_over(SlideSpare(index=number, slide=deck_slide))

    def _go_on(self) -> None:
        if self.cancelled.is_set():
            raise TalkCancelled()


class _Stages:
    """How far a talk is (see talkgenerator.models.events.TalkProgress), as its Progress is told: from its start, that
    it started (talk.started), how far its language model is (see Planning) and every slide it settled; handed over as
    a talk.progress event whenever that changes, until the talk is cancelled. Its Progress tells it on whichever thread
    it's told, so it hands over one event at a time, in the order the changes came."""

    def __init__(self, hand_over: Callable[[TalkEvent], None], slides: int, cancelled: threading.Event) -> None:
        self._hand_over = hand_over
        self._cancelled = cancelled
        self._ready = [False] * max(0, slides)  # by slide number
        self._started = False
        self._planning: Planning | None = None
        self._last: TalkProgress | None = None
        self._lock = threading.Lock()

    def begin(self) -> None:
        with self._lock:
            self._tell()

    def started(self) -> None:
        with self._lock:
            self._started = True
            self._tell()

    def ready(self, slide_nr: int) -> None:
        with self._lock:
            if 0 <= slide_nr < len(self._ready):
                self._ready[slide_nr] = True
            self._tell()

    def planning(self, planning: Planning) -> None:
        with self._lock:
            self._planning = planning
            self._tell()

    def _tell(self) -> None:
        """Hand over how far the talk is, if that changed (with the lock held). How far a talk is never stops it."""
        planning = self._planning
        try:
            progress = TalkProgress(
                stage=self._stage(planning),
                slides=tuple(self._slide_stage(slide_nr, planning) for slide_nr in range(len(self._ready))),
                parts=planning.parts if planning is not None else 0,
                writes=len(planning.writes) if planning is not None else 0,
                written=len(planning.written) if planning is not None else 0,
            )
        except Exception:
            logger.exception("Telling how far the talk is crashed")
            return
        if progress != self._last and not self._cancelled.is_set():
            self._last = progress
            self._hand_over(progress)

    def _stage(self, planning: Planning | None) -> TalkStage:
        if self._ready and all(self._ready):
            return "finishing"
        if planning is not None and not planning.answered:
            if not planning.heard:
                return "asking"
            if not planning.plan_in:
                return "planning"
            if len(planning.written) < len(planning.writes):
                return "writing"
        # (once the model is asked, its slides are being made as their texts come in, before talk.started too)
        return "composing" if self._started or planning is not None else "starting"

    def _slide_stage(self, slide_nr: int, planning: Planning | None) -> SlideStage:
        if self._ready[slide_nr]:
            return "ready"
        if planning is not None and slide_nr in planning.written:
            return "written"
        if planning is not None and slide_nr in planning.planned:
            return "planned"
        return "waiting"


def palette(theme: Theme | None) -> tuple[str, ...]:
    """The colours of a theme its pictures had better go with: its accents, background and panels (none for the
    classic theme)."""
    if theme is None:
        return ()
    colors = theme.palette
    return (colors.accent, colors.accent_2, colors.background, colors.surface)


def _language_model(llm: TextProvider | str | None) -> TextProvider | None:
    """The provider to write a talk with, or None for a classic talk."""
    if llm is None:
        provider = from_settings()
    elif isinstance(llm, str):
        provider = provider_from_spec(llm)
    else:
        provider = llm
    return None if isinstance(provider, NoneProvider) else provider


def save_deck_to_json(deck: Deck, output_folder: str, file_name: str, next_to: str | None = None) -> str:
    """Save the deck as JSON: next to the given .pptx with the same name, or else as a new file in output_folder."""
    if next_to:
        path = pathlib.Path(next_to).with_suffix(".json")
    else:
        path = _unused_path(pathlib.Path(output_folder), file_name, ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(deck.to_json(), encoding="utf-8")
    logger.info("Saved the deck as JSON to {}".format(path))
    return str(path)


def _unused_path(folder: pathlib.Path, file_name: str, extension: str) -> pathlib.Path:
    for index in range(MAX_PRESENTATION_SAVE_TRIES + 1):
        path = folder / (file_name + ("_" + str(index) if index > 0 else "") + extension)
        if not path.exists():
            return path
    raise FileExistsError(f"Every name for {file_name}{extension} in {folder} is taken")


def save_presentation_to_pptx(output_folder: str, file_name: str, prs, index=0) -> str | None:
    """Save the talk."""
    if index > MAX_PRESENTATION_SAVE_TRIES:
        return None

    suffix = "_" + str(index) if index > 0 else ""
    fp: str = os.path.join(output_folder, str(file_name) + str(suffix) + ".pptx")

    # If file already exists, don't overwrite it:
    if pathlib.Path(fp).is_file():
        return save_presentation_to_pptx(output_folder, file_name, prs, index + 1)

    # Create the parent folder if it doesn't exist
    pathlib.Path(os.path.dirname(fp)).mkdir(parents=True, exist_ok=True)

    try:
        prs.save(fp)
        logger.info("Saved talk to {}".format(fp))
        return fp
    except PermissionError:
        return save_presentation_to_pptx(output_folder, file_name, prs, index + 1)


def _open_file(filename: str):
    """Platform independent open method to cover different OS."""
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


def describe_schemas() -> str:
    """A readable overview of the registered presentation schemas and the slide generators they use."""
    lines = []
    for name in schemas.names():
        generators = schemas.get(name).slide_generators
        lines.append(f"{name} ({len(generators)} slide generators)")
        lines.extend(f"    {generator}" for generator in generators)
    return "\n".join(lines)


def _license_policy(value: str) -> str:
    """--license_policy's value, once it's known to name a policy or license classes."""
    try:
        return licenses.policy(value).name
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _image_generator_spec(value: str) -> str:
    """--image_generator's value, once it's known to name an image generator."""
    try:
        generators.generator_from_spec(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return value


def _vision_pick_spec(value: str) -> str:
    """--vision_pick's value, once it's known to turn the vision pick on or off, or to name a model."""
    try:
        return vision.check_spec(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _name_styles(value: str) -> tuple[str, ...]:
    """--name_styles's value, once it's known to name only name styles there are."""
    try:
        return names.styles(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _personas(value: str) -> tuple[str, ...]:
    """--personas's value, once it's known to name only personas there are."""
    try:
        return talk_personas.allowed(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _theme_families(value: str) -> tuple[str, ...]:
    """--theme_families's value, once it's known to name only theme families there are."""
    try:
        return themes.allowed(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _llm_spec(spec: str) -> str:
    """--llm's value, once it's known to name a language model provider."""
    try:
        provider_from_spec(spec)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return spec


def str2bool(v):
    # stackoverflow.com/questions/15008758/parsing-boolean-values-with-argparse
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def get_argument_parser():
    parser = argparse.ArgumentParser(
        description="Quickly build a slide deck.",
        epilog="To check generated talks on a set of topics: talkgenerator check --help",
    )
    parser.add_argument("--topic", default="", type=str, help="Topic of presentation.")
    parser.add_argument(
        "--num_slides",
        "--slides",
        default=10,
        type=int,
        help="Number of slides to create.",
    )
    parser.add_argument(
        "--int_seed",
        default=None,
        type=int,
        help="Seed for the talk's random choices: the same seed gives the same talk, in parallel or not (as long as "
        "the sources give the same answers). Without one, a random seed is picked, and logged.",
    )
    parser.add_argument(
        "--schema",
        default="default",
        type=str,
        choices=(RANDOM, *schemas.names()),
        help="The talk's format: default (a TED-like talk), ted (with copyright-free images only), pitch, academic and "
        "the others (see --list), or random, for one the talk's seed picks after its persona, who favours some (a "
        "startup founder pitches more often); --license_policy open gives copyright-free images with any (default: "
        "default)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the presentation schemas and their slide generators, then exit.",
    )
    parser.add_argument(
        "--presenter",
        default=None,
        type=str,
        help="The full name of the presenter, leave blank to make one up (see --name_styles)",
    )
    parser.add_argument(
        "--name_styles",
        default=None,
        type=_name_styles,
        help="Without --presenter, the styles of made-up names the talk's seed picks from, separated by commas: "
        "pun (such as Prof. Anna Tomy, for a talk on medicine), fun_surname (Linda Hivesworth, for bees), famous_pun "
        "(Albert Einstone, for geology) and classic (a random first and last name, as in 2019). The language model "
        "that writes the talk writes the name; without one, talkgenerator has names of its own for some topics, and "
        "makes up a classic one otherwise (default: pun,fun_surname,famous_pun, as the talk's persona favours them)",
    )
    parser.add_argument(
        "--persona",
        default=None,
        choices=talk_personas.choices(),
        help="Who presents the talk, such as startup_founder or kindergarten_teacher: they shape which kinds of slides "
        "it favours, its title, the style of the presenter's name, the language model's voice, a random theme's family "
        "and the looks some pictures are searched in first, and with --schema random the format; none makes the "
        "format's own talk (default: random, a persona the talk's seed picks)",
    )
    parser.add_argument(
        "--personas",
        default=None,
        type=_personas,
        help="The personas the talk's seed picks from, separated by commas, such as startup_founder,consultant: a "
        "talk whose seed picks one of them keeps it, and the others get one of them (default: all of them)",
    )
    parser.add_argument(
        "--title",
        default=None,
        type=str,
        help="The title of the talk, leave blank to randomise",
    )
    parser.add_argument(
        "--topic_or_title",
        default=None,
        type=str,
        help="Instead of --topic and --title: what the talk is about or its title, such as 'penguins' or 'Why I "
        "Joined a Penguin Cult'. In quote marks, it's the title, word for word. Four words or more, or a question or "
        "exclamation, is the talk's title (its obvious slips fixed); anything shorter is the topic, on which the "
        "language model builds a funnier title. Without a model, a title is also what starts like one ('How to', "
        "'Why', 'The', 'A', 'My') or makes a claim",
    )
    parser.add_argument(
        "--license_policy",
        default=None,
        type=_license_policy,
        help="The license classes the talk's images may have: all, open (everything but fair use: no memes, gifs or "
        "Reddit's posts, for decks shown in public), or license classes separated by commas (public-domain, open, "
        "stock, generated, fair-use) (default: the schema's: open for ted, else all)",
    )
    parser.add_argument(
        "--image_generator",
        default=None,
        type=_image_generator_spec,
        help="Generates pictures, in talks a language model writes, for the slides stock photos can't show well (the "
        "presenter's weird hobby, the cover of the book they wrote, an old photo of a moment in a made-up history) and "
        "for slides whose images can't be found: openai[:<model>], openrouter[:<model>], gemini[:<model>], "
        "flux[:<model>], comfyui or automatic1111 (servers of your own, for nothing), or none. Generated pictures cost "
        "money, on your own key: a few per talk at most (see --generated_images) (default: "
        "TALKGENERATOR_IMAGE_GENERATOR's, or else none)",
    )
    parser.add_argument(
        "--generated_images",
        default=None,
        type=int,
        help="How many pictures a talk generates at most (default: TALKGENERATOR_GENERATED_IMAGES's, or else 3)",
    )
    parser.add_argument(
        "--vision_pick",
        nargs="?",
        const="on",
        default=None,
        type=_vision_pick_spec,
        help="Has a vision model pick the pictures of the slides a language model writes, each among a few "
        "candidates, which it sees side by side on one contact sheet, in one request a talk (it can refuse them all: "
        "the finder's picture then stays). Alone or 'on': the talk's own model when it reads pictures (Claude, "
        "OpenAI), else OpenRouter's free models that do (with an OpenRouter key: one more request of the free tier's "
        "a talk); or a model, as provider:model, such as anthropic:claude-haiku-5-5; or none (default: none)",
    )
    parser.add_argument(
        "--parallel",
        default=True,
        type=str2bool,
        help=("Generated powerpoint will generate in parallel " + "faster but drops some conditions)"),
    )
    parser.add_argument(
        "--print_logs",
        default=True,
        type=str2bool,
        help="Print logs about the generation process.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print debug logs as well (very chatty).",
    )
    parser.add_argument(
        "--debug_notes",
        action="store_true",
        help="Explain in each slide's speaker notes how it was generated (presenters can see these!).",
    )
    parser.add_argument(
        "--output_folder",
        default=DEFAULT_OUTPUT_FOLDER,
        type=str,
        help="The folder to output the generated presentations (default: ./output)",
    )
    parser.add_argument(
        "--save_ppt",
        default=True,
        type=str2bool,
        help="If this flag is true, the generated powerpoint will be saved",
    )
    parser.add_argument(
        "--save_json",
        default=False,
        type=str2bool,
        help="Also save the talk as a deck in JSON, next to the PowerPoint and with the same name",
    )
    parser.add_argument(
        "--llm",
        default=None,
        type=_llm_spec,
        help="The language model that writes the talk, as provider:model: openrouter[:<model>], anthropic[:<model>], "
        "openai:<model> or chatgpt[:<model>]; 'none' makes a classic talk (default: TALKGENERATOR_LLM's, or else "
        "your ChatGPT plan's models once you've signed in with talkgenerator login chatgpt, or else OpenRouter's free "
        "models when there's an OpenRouter key: OPENROUTER_API_KEY, or talkgenerator login openrouter)",
    )
    parser.add_argument(
        "--llm_level",
        default=None,
        choices=outline.LEVELS,
        help="How much the language model does: basic (one request a talk: it writes every slide from the word the "
        "talk's dice give it) or advanced (it first plans the talk, its thesis, a running gag and every slide's word "
        "and idea, and writes every slide in a request of its own as soon as its idea is in, in parallel: cleverer "
        "talks, as fast, for more requests) (default: TALKGENERATOR_LLM_LEVEL's, or else advanced on a model of your "
        "own that costs and basic on free models)",
    )
    parser.add_argument(
        "--theme",
        choices=themes.choices(),
        help="The look: random (a theme the seed picks, of a family the talk's persona favours more often), classic "
        "(the 2019 template), a family's name, or chaos (every slide its own theme) (default: TALKGENERATOR_THEME's, or "
        "else random)",
    )
    parser.add_argument(
        "--style_chaos",
        default=0.0,
        type=float,
        help="How many slides get a theme of their own, from 0 (none) to 1 (all) (default: 0)",
    )
    parser.add_argument(
        "--no_extreme_themes",
        dest="extreme_themes",
        action="store_false",
        help="Leave the themes for laughs, such as 1997 WordArt and Comic Sans everywhere, out of the random mix",
    )
    parser.add_argument(
        "--theme_families",
        default=None,
        type=_theme_families,
        help="The theme families a random theme can be of (and with chaos, every slide's), separated by commas, such "
        "as 'dark minimal,Swiss poster': a talk whose seed picks one of them keeps its theme, and the others get one "
        "of them (default: all of them)",
    )
    parser.add_argument(
        "--language",
        default="en",
        choices=list(languages.LANGUAGES),
        help="The language of the talk, such as en or nl (only with a language model: classic talks are English)",
    )
    parser.add_argument(
        "--open_ppt",
        default=True,
        type=str2bool,
        help="Generated powerpoint will automatically open",
    )
    return parser
