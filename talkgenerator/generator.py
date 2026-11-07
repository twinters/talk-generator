import argparse
import logging
import os
import pathlib
import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from typing import Any

from pptx.presentation import Presentation

from talkgenerator import runtime_checker, settings
from talkgenerator.design import engine, themes
from talkgenerator.llm.base import TextProvider
from talkgenerator.llm.ledger import Budget, Ledger, MeteredProvider
from talkgenerator.llm.providers import NoneProvider, from_settings, provider_from_spec
from talkgenerator.models.deck import Deck
from talkgenerator.models.events import SlideReady, TalkEvent, TalkFinished, TalkStarted
from talkgenerator.plan import languages
from talkgenerator.schema.content_generators import full_name_generator
from talkgenerator.schema.presentation_schema import Progress, TalkCancelled
from talkgenerator.schema.presentation_schema_types import get_schema, schemas
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import word_frequency
from talkgenerator.util import image_util, os_util, random_util

DEFAULT_PRESENTATION_TOPIC = "cat"
DEFAULT_OUTPUT_FOLDER = "output"
MAX_PRESENTATION_SAVE_TRIES = 100

logger = logging.getLogger("talkgenerator")


def generate_presentation_using_cli_arguments(args) -> tuple[Presentation | None, SlideDeck, str | None]:
    """Make a talk with the given topic."""
    if getattr(args, "print_logs", False):
        os_util.show_logs(logger, logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)

    runtime_checker.check_runtime_environment()

    # Print status details
    logger.info("******************************************")
    logger.info("Making {} slide talk on: {}".format(args.num_slides, args.topic))

    return generate_presentation(
        schema=args.schema,
        slides=args.num_slides,
        topic=args.topic,
        title=args.title,
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
    )


def generate_presentation(
    schema: str,
    slides: int,
    topic: str | list[str] | None = None,
    title: str | None = None,
    presenter: str | None = None,
    parallel: bool = True,
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
) -> tuple[Presentation | None, SlideDeck, str | None]:
    """Generate a talk. With debug_notes, every slide's speaker notes explain how it was generated.

    With save_json, the talk is also saved as a deck (see talkgenerator.models.deck): as JSON, next to the PowerPoint
    and with the same name, or on its own in output_folder when save_ppt is off. slide_deck.to_deck() gives the same
    deck as an object.

    llm is the language model that writes the talk: a provider, a spec such as "anthropic:claude-opus-5-5", or None
    for the one TALKGENERATOR_LLM sets (without one, talks are classic). It writes in the given language, and the
    budget limits what it may cost; the deck tells what it used.

    theme is "random" (a theme of a family the seed picks, extremes such as 1997 WordArt too unless extreme_themes
    is off), "classic" (the 2019 template), a family's name such as "dark minimal", or "chaos" (every slide in a
    theme of its own): one of talkgenerator.design.themes.choices(), which catalog() describes. None is the one
    TALKGENERATOR_THEME names, or else random. style_chaos is how many slides get a theme of their own (0 to 1).

    progress follows the talk while it's made (see stream_talk, which hands it over in events)."""
    theme = theme or settings.theme()
    if theme not in themes.choices():
        raise ValueError(f"There's no theme {theme!r}; there are {', '.join(themes.choices())}")
    if print_logs:
        os_util.show_logs(logger)
    logger.info("**************************")
    logger.info("Generating presentation...")
    # Without some API keys, fewer image sources are used: say so (once), as it explains a lot about the results
    settings.report_missing_keys()

    # The talk's random choices all come from its seed (a random one if none is given), see random_util
    rng = random_util.Rng(int_seed)
    logger.info("Presentation seed: {} (pass it as int_seed to make this talk again)".format(rng.root_seed))

    # The talk's theme, from its seed too (see talkgenerator.design.themes)
    if theme == themes.CHAOS:
        theme, style_chaos = themes.RANDOM, 1.0
    chosen_theme = themes.pick(theme, rng.child("theme"), extreme_themes)
    if chosen_theme is not None:
        logger.info("Theme: {}".format(chosen_theme.name))

    # Retrieve the schema to generate the presentation with
    presentation_schema = get_schema(schema)
    logger.info("Presentation schema: {}".format(presentation_schema))

    # Generate random presenter name if no presenter name given
    if not presenter:
        with random_util.use(rng.child("presenter")):
            presenter = full_name_generator()

    if not topic:
        topic = (word_frequency.get_rarest_word(title) if title else None) or DEFAULT_PRESENTATION_TOPIC

    # Extract topics from given (possibly comma separated) topic
    if isinstance(topic, (list, tuple)):
        topics = list(topic)
    else:
        topics = [part.strip() for part in topic.split(",")]

    logger.info("Presentation topics: {}".format(topics))
    logger.info("Presentation num_slides: {}".format(slides))
    logger.info("Presentation presenter: {}".format(presenter))
    logger.info("Presentation title: {}".format(title))
    logger.info("Presentation parallel: {}".format(parallel))
    logger.info("Presentation int_seed: {}".format(int_seed))
    logger.info("Presentation save_ppt: {}".format(save_ppt))

    # The language model that writes the talk, if any; every request it gets is written down in the talk's ledger
    provider = _language_model(llm)
    languages.language(language)  # (a ValueError for a language talkgenerator doesn't know)
    ledger = Ledger()
    if provider is not None:
        logger.info("Language model: {}".format(provider.id))
    elif language != "en":
        logger.warning("Talks in other languages than English need a language model: this one is in English")

    # Generate the presentation object
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
        progress=progress,
    )
    slide_deck.usage = ledger.total()
    if provider is not None:
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
        save_deck_to_json(slide_deck.to_deck(schema_name=schema), output_folder, file_name, next_to=presentation_file)

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
    parallel: bool = True,
    int_seed: int | None = None,
    llm: TextProvider | str | None = None,
    language: str = "en",
    budget: Budget | None = None,
    theme: str | None = None,
    style_chaos: float = 0.0,
    extreme_themes: bool = True,
) -> Iterator[TalkEvent]:
    """Make a talk as generate_presentation does (the same deck, for the same options, seed and answers), handing
    over what's ready while it's made (see talkgenerator.models.events): talk.started once its title is known, a
    slide.ready for every slide as soon as it's settled, in order and laid out in the talk's theme, and talk.finished
    with the whole deck. Meanwhile, the slides after it are being made: a language model's while it writes them.

    Images are probed rather than downloaded (see talkgenerator.util.image_util.probing): a browser that shows the
    slides loads them itself. Nothing is saved: the deck in talk.finished renders as a PowerPoint
    (talkgenerator.render.powerpoint.render_pptx), which downloads them then.
    Stopping the iteration (closing the iterator, or leaving a for loop over it) stops the talk, and an error that
    stopped it comes out of the iterator."""
    events: queue.SimpleQueue[TalkEvent | None] = queue.SimpleQueue()  # (None: the end)
    following = _Following(events.put)
    failures: list[BaseException] = []

    def make() -> None:
        try:
            with image_util.probing():
                _, slide_deck, _ = generate_presentation(
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
                )
                events.put(TalkFinished(deck=slide_deck.to_deck(schema_name=schema)))
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
    """Turns a talk's progress into events (see stream_talk), and stops the talk once they're not wanted anymore."""

    def __init__(self, hand_over: Callable[[TalkEvent], None]) -> None:
        self.hand_over = hand_over
        self.cancelled = threading.Event()
        self._layout: engine.DeckLayout | None = None
        self._handed_over = 0

    def started(self, slide_deck: SlideDeck) -> None:
        self._go_on()
        theme = slide_deck.theme
        if theme is not None:  # (laid out one by one as they come, as to_deck lays them all out)
            self._layout = engine.DeckLayout(slide_deck.seed, theme, slide_deck.style_chaos, slide_deck.extreme_themes)
        self.hand_over(
            TalkStarted(
                title=slide_deck.title,
                presenter=slide_deck.presenter,
                topics=slide_deck.topics,
                language=slide_deck.language,
                seed=slide_deck.seed,
                slides=slide_deck.size,
                theme=theme.name if theme is not None else "classic",
                style=theme,
            )
        )

    def settled(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
        self._go_on()
        deck_slide = slide.to_deck_slide()
        if self._layout is not None:
            deck_slide = self._layout.next(deck_slide)
        self.hand_over(SlideReady(index=self._handed_over, slide=deck_slide))
        self._handed_over += 1
        # A slide shown is a slide used, which some sources want to hear of (a download, at Unsplash), as a PowerPoint
        # tells them when it gets the slide. (A PowerPoint made later from the deck doesn't tell them again.)
        for image in slide.image_store().values():
            image.mark_used()

    def _go_on(self) -> None:
        if self.cancelled.is_set():
            raise TalkCancelled()


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
        choices=schemas.names(),
        help="The presentation schema to generate the presentation with (see --list)",
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
        help="The full name of the presenter, leave blank to randomise",
    )
    parser.add_argument(
        "--title",
        default=None,
        type=str,
        help="The title of the talk, leave blank to randomise",
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
        "--theme",
        choices=themes.choices(),
        help="The look: random (a theme the seed picks), classic (the 2019 template), a family's name, or chaos "
        "(every slide its own theme) (default: TALKGENERATOR_THEME's, or else random)",
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
