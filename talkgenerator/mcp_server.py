"""talkgenerator as a local MCP server, for Claude Desktop and other MCP clients (docs/v5-plan.md, section 6).

`talkgenerator mcp` serves its tools over stdio. The client starts it on the user's own computer, where it makes talks
with the user's own keys (from the settings, as everywhere: environment variables, such as those in the client's
config, or a .env file) and saves them in an output folder of the user's choosing (--output_folder). Nothing of it is
hosted, so no one else's requests reach those keys and quotas (decision D20).

The tools are a thin layer over what the Skill's commands do (talkgenerator.plan.external): the formats and the slides
a plan for one can have, the plan's JSON Schema, and rendering a plan, as well as making a whole talk on a topic, as
`talkgenerator --topic` does. They answer in JSON, with the paths of the files they saved, and never with a key.

It needs the MCP SDK: pip install 'talkgenerator[mcp]'.
"""

import argparse
import logging
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Final, TypeVar

import anyio
import anyio.to_thread
import platformdirs
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from talkgenerator import __version__, names, settings
from talkgenerator.checks.deck import check_deck, deck_metrics
from talkgenerator.design import themes
from talkgenerator.llm import providers
from talkgenerator.llm.base import TextProvider
from talkgenerator.models.plan import TalkPlan
from talkgenerator.plan import external, languages
from talkgenerator.schema.presentation_schema_types import schemas
from talkgenerator.util import os_util

logger = logging.getLogger("talkgenerator")

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

MAX_SLIDES: Final = 40  # for a talk on a topic: a guard against a typo that would keep the sources busy for an hour
PROGRESS_EVERY: Final = 5.0  # seconds between the notifications that say a talk is still being made

# What the client may tell its model about the server, besides the tools' own descriptions (after the Skill, skill/)
INSTRUCTIONS: Final = """\
talkgenerator makes PowerPoint decks for improvised presentations, such as PowerPoint karaoke and fake TED talks, \
with images it may use, credited on the slides. The decks are saved on this computer. The presenter shouldn't see the \
slides beforehand, so say where a deck is saved, and don't describe its slides unless asked.

generate_talk has talkgenerator write a whole talk on a topic, on its own. Or write the talk yourself, to make it \
what the user asked for: look up the slides of a format with describe_format (list_formats has the formats, themes \
and languages), write a plan (its JSON Schema is in get_plan_schema and in render_plan's input), and render it with \
render_plan. Its report says per slide whether it came out as planned, and what every image was searched with and what it shows. Fix the \
slides that didn't come out and the image queries that found the wrong thing, then render again with the report's \
seed, which keeps the rest as it was. Render at most three times in all: a classic slide or an odd image is part of \
the game.

A good plan has short texts (titles of a few words, captions of one to four) written straight, like a confident \
expert; slides that raise a question for the presenter to answer, rather than finished jokes; one absurd thesis, with \
callbacks to earlier slides; the arc of a talk (who the presenter is, some history, bold claims, a chart or two, \
conclusions that call back); image queries of one to three common English words for one subject (the texts may be in \
the talk's language); and a concept for every slide with images. Plans hold search queries, never image addresses.

Keep it kind: no quotes put in the mouths of real people, nothing about private persons, and nothing that mocks people \
for who they are. Turn a hateful or harmful topic down kindly, and offer a harmless one nearby."""

_LOOKS_UP: Final = ToolAnnotations(read_only_hint=True, open_world_hint=False)
# Making a talk searches the web for images and saves new files (under new names: it never overwrites one)
_MAKES_A_TALK: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)


def default_output_folder() -> Path:
    """Where the tools save talks unless --output_folder says otherwise: a folder in the user's documents (not one
    relative to where the server runs, as MCP clients start their servers in folders of their own)."""
    return Path(platformdirs.user_documents_dir()) / "talkgenerator"


def output_folder_of(output_folder: str | Path | None) -> Path:
    """The folder the tools save talks in, as an absolute path: the one given, or else default_output_folder()."""
    return Path(output_folder or default_output_folder()).expanduser().resolve()


def make_server(output_folder: str | Path | None = None, *, progress_every: float = PROGRESS_EVERY) -> MCPServer:
    """The MCP server, whose tools save what they make in output_folder (see output_folder_of) and nowhere else, and
    tell the client every progress_every seconds that a talk is still being made."""
    folder = output_folder_of(output_folder)
    one_at_a_time = threading.Lock()  # talks are made one by one, so they don't race each other for the sources
    server = MCPServer(
        "talkgenerator",
        title="talkgenerator",
        description="Makes PowerPoint decks for improvised presentations, such as PowerPoint karaoke",
        instructions=INSTRUCTIONS,
        website_url="https://github.com/twinters/talk-generator",
        version=__version__,
    )

    def tool(title: str, annotations: ToolAnnotations) -> Callable[[F], F]:
        """server.tool, with the function's docstring as the description, on one line (as it's sent as written)."""

        def register(function: F) -> F:
            description = " ".join((function.__doc__ or "").split())
            server.tool(title=title, description=description, annotations=annotations)(function)
            return function

        return register

    @tool("List the talk formats, themes and languages", _LOOKS_UP)
    def list_formats() -> dict[str, Any]:
        """The talk formats (such as 'default', with images from every source, and 'ted', with copyright-free images
        only, for decks shown in public), the themes (the looks a talk can have), the languages it can be in, and the
        styles of the presenter's names that generate_talk makes up."""
        return {
            "formats": [{"format": name, "description": external.FORMATS.get(name, "")} for name in schemas.names()],
            "themes": themes.catalog(),
            "languages": [{"code": code, "name": language.name} for code, language in languages.LANGUAGES.items()],
            "name_styles": names.catalog(),
        }

    @tool("Describe the slides of a talk format", _LOOKS_UP)
    def describe_format(
        format: Annotated[str, Field(description="The talk format, such as 'ted' (see list_formats)")] = "default",
    ) -> dict[str, Any]:
        """The slides a plan for a talk format can have: every kind of slide with its texts (and their length limits)
        and its images, and the recipes that pick a slide's look and image sources (the same as `talkgenerator formats
        --details --json`)."""
        _check("format", format, schemas.names())
        return external.catalog(format)

    @tool("Get the JSON Schema of talk plans", _LOOKS_UP)
    def get_plan_schema() -> dict[str, Any]:
        """The JSON Schema of the talk plans that render_plan takes (as `talkgenerator schema plan` prints it)."""
        return TalkPlan.model_json_schema()

    @tool("Render a talk plan as a PowerPoint", _MAKES_A_TALK)
    async def render_plan(
        ctx: Context,
        plan: Annotated[TalkPlan, Field(description="The talk: see describe_format for the slides it can have")],
        presenter: Annotated[
            str | None,
            Field(description="The presenter's name, for the title slide (without one, talkgenerator makes one up)"),
        ] = None,
        seed: Annotated[
            int | None,
            Field(
                description="The seed of an earlier render of this plan, which keeps the images of what didn't change"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Turn a talk plan into a PowerPoint. talkgenerator finds images for the plan's queries and credits them,
        makes a slide that doesn't come out as planned the classic way instead, and saves the PowerPoint with the
        deck's JSON and a contact sheet of its images (a PNG) next to it. Returns the report, with the files' paths:
        per planned slide its outcome ('as planned', 'classic', 'picture' or 'left out'), its problems and warnings,
        and what every image was searched with and shows; the checks; and the seed, to render the plan again. This
        takes a few seconds to a minute."""
        problem = external.plan_error(plan)
        if problem is not None:
            raise ToolError(problem)

        def render() -> dict[str, Any]:
            return external.render_plan(
                plan,
                schema_name=plan.format or "default",
                presenter=presenter or None,
                int_seed=seed,
                output_folder=folder,
            )

        return await _in_a_thread(ctx, "Rendering the plan", render, one_at_a_time, progress_every, folder)

    @tool("Make a talk on a topic", _MAKES_A_TALK)
    async def generate_talk(
        ctx: Context,
        topic: Annotated[
            str | None,
            Field(min_length=1, description="What the talk is about, such as 'peanuts' (or topics, with commas)"),
        ] = None,
        topic_or_title: Annotated[
            str | None,
            Field(
                min_length=1,
                description="Instead of a topic and a title: what the user asked for, as they put it, when it could "
                "be either, such as 'penguins' or 'Why I Joined a Penguin Cult' (four words or more, or a question, "
                "stays the title with only its obvious slips fixed; anything shorter is the topic, which gets a "
                "funnier title)",
            ),
        ] = None,
        slides: Annotated[int, Field(ge=2, le=MAX_SLIDES, description="How many slides, the title slide too")] = 10,
        format: Annotated[str, Field(description="The talk format (see list_formats)")] = "default",
        language: Annotated[
            str,
            Field(
                description="The language of its texts, such as 'en' or 'nl' (only a language model writes talks in "
                "other languages than English)"
            ),
        ] = "en",
        theme: Annotated[
            str | None,
            Field(
                description="The look: 'random', 'classic' (the 2019 template), a theme family, or 'chaos' (see "
                "list_formats; without one, the user's settings', or else random)"
            ),
        ] = None,
        title: Annotated[str | None, Field(description="The talk's title (without one, it gets one)")] = None,
        presenter: Annotated[
            str | None,
            Field(description="The presenter's name, for the title slide (without one, talkgenerator makes one up)"),
        ] = None,
        name_styles: Annotated[
            list[str] | None,
            Field(
                description="Without a presenter, the styles of made-up names the talk's seed picks from: 'pun' (such "
                "as Prof. Anna Tomy, for a talk on medicine), 'fun_surname' (Linda Hivesworth, for bees), "
                "'famous_pun' (Albert Einstone, for geology) and 'classic' (a random first and last name); see "
                "list_formats (without them, the first three)"
            ),
        ] = None,
        seed: Annotated[int | None, Field(description="The seed of an earlier talk, to make it again")] = None,
    ) -> dict[str, Any]:
        """Make a whole talk on a topic, as `talkgenerator --topic` does (or with a title, or on a topic_or_title). The
        language model the user's settings name writes it (OpenRouter's free models, when there's an OpenRouter key),
        or else the classic 2019 generator. Saves the PowerPoint with the deck's JSON and a contact sheet of its images
        (a PNG) next to it, and returns where, with the talk's title, seed and language model, how many slides the
        model wrote, and the checks. This takes up to a minute or two."""
        if topic_or_title is not None and (topic is not None or title is not None):
            raise ToolError("give topic_or_title instead of a topic and a title, not with them")
        if topic is None and title is None and topic_or_title is None:
            raise ToolError("give a topic, a title or a topic_or_title")
        _check("format", format, schemas.names())
        if theme is not None:
            _check("theme", theme, themes.choices())
        _check("language", language, list(languages.LANGUAGES))
        for style in name_styles or ():
            _check("name style", style, list(names.STYLES))
        try:
            model = providers.from_settings()  # never from the tool's arguments: only the user picks a paid model
        except ValueError as error:
            raise ToolError(f"the language model the settings ask for can't be used: {error}") from error

        def generate() -> dict[str, Any]:
            return _generate(
                model,
                folder,
                topic,
                slides,
                format,
                language,
                theme,
                title,
                presenter,
                seed,
                name_styles,
                topic_or_title,
            )

        return await _in_a_thread(ctx, "Making the talk", generate, one_at_a_time, progress_every, folder)

    return server


def _check(what: str, value: str, choices: Sequence[str]) -> None:
    problem = external.unknown_choice(what, value, choices)
    if problem is not None:
        raise ToolError(problem)


def _generate(
    model: TextProvider,
    folder: Path,
    topic: str | None,
    slides: int,
    schema_name: str,
    language: str,
    theme: str | None,
    title: str | None,
    presenter: str | None,
    seed: int | None,
    name_styles: Sequence[str] | None = None,
    topic_or_title: str | None = None,
) -> dict[str, Any]:
    """A talk on a topic (or with a title, or on a topic_or_title), saved in the folder with its deck's JSON and
    contact sheet, and the report on it."""
    from talkgenerator import generator  # (here: the generator module imports the schemas)

    _, slide_deck, saved = generator.generate_presentation(
        schema=schema_name,
        slides=slides,
        topic=topic or None,
        title=title or None,
        topic_or_title=topic_or_title or None,
        presenter=presenter or None,
        int_seed=seed,
        output_folder=str(folder),
        open_ppt=False,
        llm=model,
        language=language,
        theme=theme,
        name_styles=name_styles,
    )
    if saved is None:
        raise ToolError(f"couldn't save the PowerPoint in {folder}")
    pptx = Path(saved)
    deck = slide_deck.to_deck(schema_name=schema_name)
    deck_json = pptx.with_name(pptx.stem + ".deck.json")
    deck_json.write_text(deck.to_json(), encoding="utf-8")
    sheet = pptx.with_name(pptx.stem + ".images.png")
    has_sheet = external.save_contact_sheet(slide_deck, deck, sheet)

    writes = not isinstance(model, providers.NoneProvider)
    written = deck_metrics(deck)["written_by_language_model"]
    report: dict[str, Any] = {
        "pptx": str(pptx),
        "deck_json": str(deck_json),
        "contact_sheet": str(sheet) if has_sheet else None,
        "title": deck.title,
        "presenter": deck.presenter,
        "topics": list(deck.topics),
        "format": schema_name,
        "language": deck.language,
        "theme": deck.theme,
        "seed": deck.seed,
        "language_model": model.id if writes else None,  # None: the classic generator
        "summary": {"deck_slides": len(deck.slides), "written_by_language_model": written},
        "usage": deck.usage.model_dump(),
        "checks": [asdict(finding) for finding in check_deck(deck, slides)],
        "sources_without_keys": settings.sources_without_keys(),
    }
    if deck.topic_or_title is not None:  # (how what was typed was read: as the topic or as the title)
        report["topic_or_title"] = deck.topic_or_title.model_dump()
    notes = []
    if writes and not written:
        notes.append("the language model wrote none of the slides, so the talk is classic (the server's log says why)")
    if deck.language != language:
        notes.append(
            "talks in other languages than English need slides a language model wrote, and this one has none, so it's "
            "in English" + ("" if writes else " (the settings name no language model)")
        )
    if notes:
        report["notes"] = notes
    return report


async def _in_a_thread(
    ctx: Context, doing: str, work: Callable[[], T], lock: threading.Lock, every: float, folder: Path
) -> T:
    """Do the work in a worker thread, one talk at a time, and meanwhile tell the client every so many seconds that it
    goes on: a client that asked for progress then knows to keep waiting, and can show it."""

    def one_at_a_time() -> T:
        with lock:
            try:
                return work()
            except OSError as error:  # (most likely: the folder can't be written to)
                raise ToolError(f"couldn't save the talk in {folder}: {error}") from error

    done = anyio.Event()
    outcome: list[T] = []
    failures: list[Exception] = []

    async def do_it() -> None:
        try:
            outcome.append(await anyio.to_thread.run_sync(one_at_a_time))
        except Exception as error:  # raised below, outside the task group, which would wrap it in an exception group
            failures.append(error)
        finally:
            done.set()

    async with anyio.create_task_group() as group:
        group.start_soon(do_it)
        seconds = 0.0
        while True:
            with anyio.move_on_after(every):
                await done.wait()
            if done.is_set():
                break
            seconds += every
            try:
                await ctx.report_progress(seconds, message=f"{doing}: {seconds:.0f} seconds so far")
            except Exception:  # a client that went away: the talk still gets saved
                logger.debug("Couldn't report progress", exc_info=True)
    if failures:
        raise failures[0]
    return outcome[0]


def main(argv: Sequence[str]) -> int:
    """`talkgenerator mcp`: serve the tools over stdio, until the client stops the server."""
    parser = argparse.ArgumentParser(
        prog="talkgenerator mcp",
        description="Serve talkgenerator's tools to Claude Desktop and other MCP clients, over stdio, on this computer: "
        "they make talks with the keys of your settings, and save them in the output folder. MCP clients start this "
        "command themselves (see the README).",
    )
    parser.add_argument(
        "--output_folder", help=f"where the talks are saved, and nowhere else (default: {default_output_folder()})"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="log debug messages too (on stderr, as all logs)")
    args = parser.parse_args(argv)

    # Logs go to stderr, which MCP clients keep in a log file: stdout carries the protocol
    os_util.show_logs(logger, logging.DEBUG if args.verbose else logging.INFO, stream=sys.stderr)
    folder = output_folder_of(args.output_folder)
    server = make_server(folder)
    logger.info("talkgenerator %s serves its MCP tools over stdio; talks are saved in %s", __version__, folder)
    try:
        server.run("stdio")
    except KeyboardInterrupt:  # (run in a terminal, and stopped there)
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
