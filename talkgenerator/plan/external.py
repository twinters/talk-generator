"""Plans written outside talkgenerator: by Claude through the Skill (skill/), or by hand (docs/v5-plan.md, section 6).

An agent asks for the plan format (`talkgenerator schema plan`) and the slides it can plan (`talkgenerator formats
--details`), writes a plan as JSON, and renders it (`talkgenerator render plan.json`). talkgenerator then finds and
credits the images for the plan's queries, has a slide that doesn't come out made by its recipe's classic generator
instead, saves the PowerPoint and the deck's JSON, and prints a report in JSON that says what to fix.

A slide's recipe is one of the format's slide generators: it picks the slide's look and image sources (gifs, memes,
old photos, ...), and makes the slide the classic way when the plan's version can't be made. Recipes go by an id
made from their generator's name, such as "two-captions-gifs" for "Two Captions Gifs".
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import logging
import os
import re
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from talkgenerator import settings
from talkgenerator.checks.deck import check_deck
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.models.deck import Deck, ImageElement, TextElement
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, PRESENTER_JOB, TALK_TITLE, Recipe, TextField
from talkgenerator.plan.realize import length_limit, option_of
from talkgenerator.schema.presentation_schema import PlanOutcome, PresentationSchema
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import os_util, random_util

logger = logging.getLogger("talkgenerator")

# What the formats (for now, the presentation schemas) are for
FORMATS: Final = {
    "default": "A TED-like talk: about the presenter, history, bold statements, captioned images, charts and "
    "conclusions, with images from every source (memes and gifs too)",
    "ted": "A TED-like talk with copyright-free images only (stock photos, artworks and old photos), for decks "
    "shown in public; it has no full-screen images, gifs or memes, and no recipes for slides about the presenter",
    "interview": "The TED-like talk, without slides about the presenter",
    "test": "For testing talkgenerator itself",
}

# The recipe a kind of slide gets when its plan doesn't name one, the first of these the format has: plain photos,
# which need no Reddit or GIPHY key, and texts the plan writes (some recipes find their texts themselves, such as
# real quotes). A format without any of them borrows a copyright-free one, as those images are fine in every format.
_DEFAULT_RECIPES: Final = {
    "image": ("single-image-copyright-free",),
    "full_image": ("full-screen-neutral-images",),
    "statement": ("wikihow-bold-statement", "wikihow-bold-statement-crf"),
    "two_columns": ("two-captions-copyright-free",),
    "three_columns": ("three-captions-weird-crf",),
    "history_quote": ("historical-figure-quote-crf",),  # portraits and stock photos, not Reddit's photos of real people
    "chart_yes_no": ("yes-no-funny-chart",),
    "chart_categories": ("property-chart",),
    "chart_correlation": ("correlation-curve",),
    "chart_trend": ("trend-chart",),
    "chart_bars": ("bar-ranking",),
}
_COPYRIGHT_FREE: Final = re.compile(r"-crf$|copyright-free")
PLANNABLE_KINDS: Final = tuple(name for name in KINDS if name != "title")
_URL: Final = re.compile(r"^\s*https?://", re.IGNORECASE)


@dataclass(frozen=True, eq=False)
class RecipeChoice:
    id: str
    generator: SlideGeneratorData
    recipe: Recipe


def recipe_id(name: str) -> str:
    """The id of a slide generator's recipe: its name in lowercase, with dashes, such as "two-captions-gifs"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def recipes_of(schema: PresentationSchema) -> list[RecipeChoice]:
    """The recipes a plan for this schema can pick from: those of its slide generators (but the title slide's), and
    a copyright-free default for a kind that has none of its default recipes."""
    from talkgenerator.schema.slide_schemas import slide_generators  # every registered slide generator

    own = _choices(schema.slide_generators)
    everywhere = _choices(slide_generators)
    borrowed = []
    for kind, preferred in _DEFAULT_RECIPES.items():
        if any(choice.id in preferred and choice.recipe.kind == kind for choice in own):
            continue
        for choice in everywhere:
            if choice.id in preferred and choice.recipe.kind == kind and _COPYRIGHT_FREE.search(choice.id):
                borrowed.append(choice)
                break
    return own + borrowed


def _choices(generators: Any) -> list[RecipeChoice]:
    return [
        RecipeChoice(recipe_id(generator.name or str(generator)), generator, generator.llm)
        for generator in generators
        if generator.llm is not None and generator.llm.kind != "title"
    ]


def default_recipe(choices: Sequence[RecipeChoice], kind: str) -> RecipeChoice | None:
    """The recipe of a kind of slide whose plan names none (None if the format has no slides of that kind)."""
    for wanted in _DEFAULT_RECIPES.get(kind, ()):
        for choice in choices:
            if choice.id == wanted and choice.recipe.kind == kind:
                return choice
    writes_its_texts = [choice for choice in choices if choice.recipe.kind == kind and not choice.recipe.texts_from]
    return writes_its_texts[0] if writes_its_texts else None


def choose_recipe(
    choices: Sequence[RecipeChoice], slide: SlidePlan, language: str = "en"
) -> tuple[RecipeChoice | None, list[str]]:
    """The recipe a planned slide gets (None if it can't be made), and warnings about the one it asked for. In a
    talk in another language than English, that's never one that finds its texts itself: they'd be English."""
    if slide.kind not in PLANNABLE_KINDS:
        return None, [f"there's no slide kind {slide.kind!r}; the kinds are {', '.join(PLANNABLE_KINDS)}"]
    warnings = []
    if slide.recipe:
        found = next((choice for choice in choices if choice.id == recipe_id(slide.recipe)), None)
        if found is None:
            warnings.append(f"this format has no recipe {slide.recipe!r}: the default one for {slide.kind} was used")
        elif found.recipe.kind != slide.kind:
            warnings.append(
                f"recipe {slide.recipe!r} makes {found.recipe.kind} slides, not {slide.kind} ones: the default one "
                f"for {slide.kind} was used"
            )
        elif language != "en" and found.recipe.texts_from:
            warnings.append(
                f"recipe {slide.recipe!r} finds English texts, which don't fit a talk in another language: the "
                f"default one for {slide.kind} was used"
            )
        else:
            return found, warnings
    choice = default_recipe(choices, slide.kind)
    if choice is None:
        return None, [*warnings, f"this format has no {slide.kind} slides"]
    return choice, warnings


def plan_warnings(slide: SlidePlan, recipe: Recipe) -> list[str]:
    """What in a planned slide won't show up as written: texts its kind doesn't have or its recipe doesn't use,
    texts too long for their place, images the kind doesn't have, and image addresses instead of queries."""
    kind = KINDS[recipe.kind]
    fields = {text.name: text for text in kind.texts}
    warnings = []
    for name, value in slide.texts.items():
        text_field = fields.get(name)
        if text_field is None:
            warnings.append(f"{kind.name} slides have no text {name!r}; they have {_listed(fields)}")
        elif name in recipe.omit:
            warnings.append(f"this recipe shows no {name}")
        elif name in recipe.texts_from:
            warnings.append(f"this recipe finds its {name} itself, so yours isn't used")
        elif text_field.options and value.strip() and option_of(value, text_field) is None:
            warnings.append(
                f"{name} is none of {_listed(text_field.options)}, so "
                + ("talkgenerator picked one" if text_field.optional else "the slide can't be made")
            )
        elif len(" ".join(value.split())) > length_limit(text_field):
            warnings.append(f"{name} has more than {text_field.max_length} characters, so it was cut off")
    for slot, query in slide.images.items():
        if slot not in kind.images:
            warnings.append(f"{kind.name} slides have no image {slot!r}; they have {_listed(kind.images)}")
        elif _URL.match(query):
            warnings.append(f"{slot} is an address: images are searched for with words (or are files of your own)")
    for slot in recipe.image_queries():
        if not slide.images.get(slot, "").strip():
            warnings.append(f"no query for {slot}, so it was searched for with the concept")
    return warnings


def _listed(names: Any) -> str:
    listed = [repr(name) for name in names]
    return ", ".join(listed) if listed else "none"


# RENDERING A PLAN


def render_plan(
    plan: TalkPlan,
    *,
    schema_name: str = "default",
    presenter: str | None = None,
    int_seed: int | None = None,
    output: str | Path | None = None,
    output_folder: str | Path = "output",
    file_name: str | None = None,
    save_json: bool = True,
    contact_sheet: bool = True,
    plan_path: Path | None = None,
    local_images: Path | None = None,
    parallel: bool = True,
    debug_notes: bool = False,
) -> dict[str, Any]:
    """Realize a plan, save it as a PowerPoint (at output, or under an unused name in output_folder), with the deck's
    JSON (<name>.deck.json) and a contact sheet of its images (<name>.images.png) next to it, and return the report:
    what came out as planned, what didn't and why, what every image was searched with, and the checks.

    With local_images (a folder), image "queries" that name image files there put those files on the slides. Nothing
    is saved over plan_path, the plan's own file."""
    from talkgenerator import generator  # (here: the generator module imports the schemas)
    from talkgenerator.schema.content_generators import full_name_generator

    schema = generator.get_schema(schema_name)
    rng = random_util.Rng(int_seed)
    if not presenter:
        with random_util.use(rng.child("presenter")):
            presenter = full_name_generator()

    choices = recipes_of(schema)
    chosen = [choose_recipe(choices, slide, plan.language) for slide in plan.slides]
    recipes = [(choice.generator, choice.recipe) if choice else None for choice, _ in chosen]
    # The recipes as chosen, which the slides' notes then name
    resolved = tuple(
        slide.model_copy(update={"recipe": choice.id}) if choice else slide
        for slide, (choice, _) in zip(plan.slides, chosen, strict=True)
    )
    slide_deck, outcomes = schema.realize_plan(
        plan.model_copy(update={"slides": resolved}), recipes, presenter, rng, local_images, parallel
    )
    deck = slide_deck.to_deck(schema_name=schema_name)

    name = file_name or _file_name(plan.title or plan.topic)
    pptx = Path(_save(schema.render(slide_deck, debug_notes), output, Path(output_folder), name))
    notes: list[str] = []
    deck_json = sheet = None
    if save_json:
        deck_json = _beside(pptx, ".deck.json", plan_path, notes)
        if deck_json is not None:
            deck_json.write_text(deck.to_json(), encoding="utf-8")
    if contact_sheet:
        sheet = _beside(pptx, ".images.png", plan_path, notes)
        if sheet is not None and not save_contact_sheet(slide_deck, deck, sheet):
            sheet = None

    slide_reports = []
    deck_slide = 1  # the title slide
    for index, (slide, (choice, warnings), outcome) in enumerate(zip(plan.slides, chosen, outcomes, strict=True)):
        if outcome.outcome != "left out":
            deck_slide += 1
        number = deck_slide if outcome.outcome != "left out" else None
        slide_reports.append(_slide_report(index, slide, choice, warnings, outcome, deck, number))
    outcome_names = [report["outcome"] for report in slide_reports]
    report: dict[str, Any] = {
        "pptx": str(pptx),
        "deck_json": str(deck_json) if deck_json else None,
        "contact_sheet": str(sheet) if sheet else None,
        "title": deck.title,
        "presenter": presenter,
        "format": schema_name,
        "language": deck.language,
        "seed": rng.root_seed,
        "summary": {
            "deck_slides": len(deck.slides),  # the title slide too
            "planned_slides": len(plan.slides),
            "as_planned": outcome_names.count("as planned"),
            "classic": outcome_names.count("classic"),
            "picture": outcome_names.count("picture"),
            "left_out": outcome_names.count("left out"),
        },
        "slides": slide_reports,
        "checks": [asdict(finding) for finding in check_deck(deck)],
        "sources_without_keys": settings.sources_without_keys(),
    }
    for text_field in (TALK_TITLE, PRESENTER_JOB):
        if len(" ".join(getattr(plan, text_field.name).split())) > length_limit(text_field):
            notes.append(f"the {text_field.name} has more than {text_field.max_length} characters, so it was cut off")
    if notes:
        report["notes"] = notes
    return report


def _beside(pptx: Path, suffix: str, plan_path: Path | None, notes: list[str]) -> Path | None:
    """The path of a file that goes with the PowerPoint, unless that's where the plan is."""
    path = pptx.with_name(pptx.stem + suffix)
    if plan_path is not None and path.resolve() == plan_path.resolve():
        notes.append(f"{path} is the plan itself, so the {suffix} file wasn't saved")
        return None
    return path


def _slide_report(
    index: int,
    slide: SlidePlan,
    choice: RecipeChoice | None,
    warnings: list[str],
    outcome: PlanOutcome,
    deck: Deck,
    deck_slide: int | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "plan_index": index,  # where it is among the plan's slides, counted from 0
        "deck_slide": deck_slide,  # where it is in the deck, counted from 1 (slide 1 is the title slide)
        "kind": slide.kind,
        "recipe": choice.id if choice else None,
        "outcome": outcome.outcome,
    }
    if deck_slide is not None:
        # What every image was searched with (the plan's query, or else the slide's concept), what it shows (as its
        # source describes it), its credit, and its page
        report["images"] = [
            {
                "searched": element.image.query,
                "shows": element.image.description,
                "credit": element.image.source or "your file",
                "page": element.image.source_url,
            }
            for element in deck.slides[deck_slide - 1].elements
            if isinstance(element, ImageElement)
        ]
    if outcome.problems:
        # For a slide that came out as planned, what failed in the tries before the one that worked
        report["problems" if outcome.outcome != "as planned" else "retried_because"] = outcome.problems
    if choice is not None:
        warnings = [*warnings, *plan_warnings(slide, choice.recipe)]
    if warnings:
        report["warnings"] = warnings
    return report


def _file_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:60] or "talk"


def _save(presentation: Any, output: str | Path | None, folder: Path, name: str) -> str:
    """Save the PowerPoint: at output (again, if it's there already), or under an unused name in the folder."""
    from talkgenerator import generator

    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            presentation.save(str(path))
            return str(path)
        except PermissionError:  # open in PowerPoint, say
            logger.warning("Can't write %s (is it open?): saving it under another name", path)
            folder, name = path.parent, path.stem
    saved = generator.save_presentation_to_pptx(str(folder), name, presentation)
    if saved is None:
        raise OSError(f"Couldn't save the PowerPoint in {folder}")
    return saved


_THUMBNAIL: Final = (240, 160)
_LABEL_LINES: Final = 4
_LINE_HEIGHT: Final = 16


def save_contact_sheet(slide_deck: SlideDeck, deck: Deck, path: Path) -> bool:
    """Save every image of the deck in one picture, each with its slide's number and texts and what it was searched
    with, to see at a glance whether the images fit (anyone who can look at a picture, an agent too). False when the
    deck has no images to show."""
    from PIL import Image, ImageDraw, ImageFont

    stored = slide_deck.image_store()
    tiles = []
    for number, slide in enumerate(deck.slides, 1):
        texts = " / ".join(element.text for element in slide.elements if isinstance(element, TextElement))
        for element in slide.elements:
            if not isinstance(element, ImageElement):
                continue
            picture = _picture(element.image.url, stored)
            if picture is not None:
                searched = f": {element.image.query}" if element.image.query else ""
                lines = [f"slide {number}{searched}", *textwrap.wrap(texts, 38)]
                tiles.append((picture, lines[:_LABEL_LINES]))
    if not tiles:
        return False

    font = ImageFont.load_default(size=13)
    columns = min(4, len(tiles))
    width, height = _THUMBNAIL[0] + 20, _THUMBNAIL[1] + 10 + _LABEL_LINES * _LINE_HEIGHT + 20
    sheet = Image.new("RGB", (columns * width + 20, -(-len(tiles) // columns) * height + 20), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (picture, lines) in enumerate(tiles):
        x, y = 20 + (index % columns) * width, 20 + (index // columns) * height
        picture.thumbnail(_THUMBNAIL)
        sheet.paste(picture, (x, y))
        for line_number, line in enumerate(lines):
            draw.text((x, y + _THUMBNAIL[1] + 8 + line_number * _LINE_HEIGHT), line, fill="black", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return True


def _picture(url: str, stored: dict[str, ImageData]) -> Any:
    """An image of the deck, from the bytes downloaded for it (or its file), as a picture; None if it won't open."""
    from PIL import Image

    data = stored[url].data if url in stored else None
    try:
        picture = Image.open(io.BytesIO(data)) if data else Image.open(url) if Path(url).is_file() else None
        return picture.convert("RGB") if picture is not None else None  # (a gif's first frame)
    except Exception:  # a picture Pillow can't read: the deck still has it, the sheet doesn't
        logger.debug("Can't show %s on the contact sheet", url, exc_info=True)
        return None


# WHAT A PLAN CAN HOLD


def catalog(schema_name: str = "default") -> dict[str, Any]:
    """The slide kinds a plan for the format can have: their texts, images and recipes."""
    from talkgenerator import generator

    choices = recipes_of(generator.get_schema(schema_name))
    kinds = []
    for name in PLANNABLE_KINDS:
        of_kind = [choice for choice in choices if choice.recipe.kind == name]
        if not of_kind:
            continue
        default = default_recipe(choices, name)
        kind = KINDS[name]
        kinds.append(
            {
                "kind": name,
                "description": kind.description,
                "texts": [_text_entry(text) for text in kind.texts],
                "images": list(kind.images),
                "recipes": [_recipe_entry(choice, choice is default) for choice in of_kind],
            }
        )
    return {"format": schema_name, "description": FORMATS.get(schema_name, ""), "kinds": kinds}


def _text_entry(text: TextField) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": text.name,
        "max_length": text.max_length,
        "optional": text.optional,
        "description": text.description,
    }
    if text.options:
        entry["options"] = list(text.options)
    return entry


def _recipe_entry(choice: RecipeChoice, is_default: bool) -> dict[str, Any]:
    recipe = choice.recipe
    entry: dict[str, Any] = {
        "id": choice.id,
        "for": recipe.brief or KINDS[recipe.kind].description,
        "default": is_default,
        "tags": sorted(choice.generator.get_tags()),
    }
    if recipe.hints:
        entry["hints"] = dict(recipe.hints)
    if recipe.omit:
        entry["leaves_out"] = sorted(recipe.omit)
    if recipe.texts_from:
        entry["finds_itself"] = sorted(recipe.texts_from)
    return entry


def catalog_markdown(schema_name: str = "default") -> str:
    """The catalog as Markdown, for people and for the Skill's reference (skill/.../references/slides.md)."""
    data = catalog(schema_name)
    lines = [
        f"# The slides of a `{schema_name}` talk",
        "",
        f"{data['description']}.",
        "",
        "Every talk starts with a title slide, made from the plan's `title` and `presenter_job` (talkgenerator adds "
        "the presenter's name). The plan's `slides` come after it, each of one of the kinds below. A slide's `recipe` "
        "picks its look and its image sources, and makes the slide the classic way when it can't be made as "
        "planned; without one, a slide gets its kind's default recipe.",
        "",
        f"Made by `talkgenerator formats --details --format {schema_name}`.",
    ]
    for kind in data["kinds"]:
        lines += ["", f"## `{kind['kind']}`", "", kind["description"], ""]
        lines += ["| Text | At most | What to write |", "| --- | --- | --- |"]
        for text in kind["texts"]:
            options = ": " + ", ".join(f"`{option}`" for option in text["options"]) if "options" in text else ""
            optional = (" (or empty, for any)" if options else " (or empty, for none)") if text["optional"] else ""
            description = _cell(text["description"]) + options + optional
            lines.append(f"| `{text['name']}` | {text['max_length']} | {description} |")
        slots = ", ".join(f"`{slot}`" for slot in kind["images"]) or "none"
        lines += ["", f"Images: {slots}", "", "| Recipe | What it's for | Notes |", "| --- | --- | --- |"]
        for recipe in kind["recipes"]:
            notes = ["the default"] if recipe["default"] else []
            notes += [f"`{name}`: {hint}" for name, hint in recipe.get("hints", {}).items()]
            for name in recipe.get("leaves_out", []):
                notes.append(f"needs no `{name}`" if name.endswith("_query") else f"shows no `{name}`")
            notes += [f"finds its `{name}` itself (don't write one)" for name in recipe.get("finds_itself", [])]
            if recipe["tags"]:
                notes.append("tags: " + ", ".join(recipe["tags"]))
            lines.append(f"| `{recipe['id']}` | {_cell(recipe['for'])} | {_cell('; '.join(notes))} |")
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


# THE COMMANDS


def main(command: str, argv: Sequence[str]) -> int:
    """`talkgenerator render`, `talkgenerator schema` and `talkgenerator formats`."""
    commands = {"render": _render_command, "schema": _schema_command, "formats": _formats_command}
    return commands[command](argv)


def _render_command(argv: Sequence[str]) -> int:
    from talkgenerator import generator
    from talkgenerator.schema.presentation_schema_types import schemas

    parser = argparse.ArgumentParser(
        prog="talkgenerator render",
        description="Turn talk plans (JSON: see `talkgenerator schema plan` and `talkgenerator formats --details`) "
        "into PowerPoints, and print a report in JSON of what came out as planned and what to fix.",
    )
    parser.add_argument("plans", nargs="+", help="plan files; patterns such as plans/*.json work too")
    parser.add_argument("-o", "--output", help="where to save the PowerPoint (with one plan)")
    parser.add_argument(
        "--output_folder", default="output", help="where to save the PowerPoints, named after their plans"
    )
    parser.add_argument("--presenter", help="the presenter's name, for the title slide (default: a made-up one)")
    parser.add_argument(
        "--format",
        dest="schema",
        choices=schemas.names(),
        help="the format (default: the plan's own, or else 'default')",
    )
    parser.add_argument(
        "--int_seed",
        type=int,
        help="seed for the random choices (such as which of the images found to use); the report gives the one used",
    )
    parser.add_argument(
        "--no_json", dest="save_json", action="store_false", help="don't save the deck's JSON next to the PowerPoint"
    )
    parser.add_argument(
        "--no_contact_sheet",
        dest="contact_sheet",
        action="store_false",
        help="don't save the picture of all the images (<name>.images.png) next to the PowerPoint",
    )
    parser.add_argument("--open", action="store_true", help="open the PowerPoint afterwards")
    parser.add_argument("--verbose", "-v", action="store_true", help="show the generator's logs (on stderr)")
    args = parser.parse_args(argv)

    paths = _expand(args.plans)
    if args.output and len(paths) > 1:
        parser.error("--output works for one plan; for more, use --output_folder")
    if args.verbose:
        os_util.show_logs(logger, stream=sys.stderr)

    reports: list[dict[str, Any]] = []
    for path in paths:
        try:
            plan = TalkPlan.model_validate_json(Path(path).read_text(encoding="utf-8"))
        except OSError as error:
            reports.append({"plan": path, "error": f"can't read it: {error}"})
            continue
        except ValidationError as error:
            details = [
                {"where": ".".join(str(part) for part in problem["loc"]) or "(the plan)", "problem": problem["msg"]}
                for problem in error.errors(include_url=False)
            ]
            reports.append(
                {"plan": path, "error": "it isn't a plan (see talkgenerator schema plan)", "details": details}
            )
            continue
        schema_name = args.schema or plan.format or "default"
        if schema_name not in schemas.names():
            formats = ", ".join(schemas.names())
            reports.append({"plan": path, "error": f"there's no format {schema_name!r}; the formats are {formats}"})
            continue
        if plan.language not in languages.LANGUAGES:
            known = ", ".join(languages.LANGUAGES)
            reports.append({"plan": path, "error": f"there's no language {plan.language!r}; the languages are {known}"})
            continue
        report = render_plan(
            plan,
            schema_name=schema_name,
            presenter=args.presenter,
            int_seed=args.int_seed,
            output=args.output,
            output_folder=args.output_folder,
            file_name=Path(path).stem,
            save_json=args.save_json,
            contact_sheet=args.contact_sheet,
            plan_path=Path(path),
            local_images=Path(path).resolve().parent,
        )
        reports.append({"plan": path, **report})
        if args.open:
            generator._open_file(os.path.realpath(report["pptx"]))

    # ASCII only: the report is for programs too, and this way no console encoding mangles it
    print(json.dumps(reports[0] if len(reports) == 1 else reports, indent=2))
    return 2 if any("error" in report for report in reports) else 0


def _expand(patterns: Sequence[str]) -> list[str]:
    """The plan files: patterns (for shells that don't expand them, such as on Windows) and plain paths."""
    paths = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern)) if glob.has_magic(pattern) else []
        paths += matches or [pattern]
    return paths


def _schema_command(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="talkgenerator schema", description="Print the JSON Schema of talk plans (plan) or of decks (deck)."
    )
    parser.add_argument("which", choices=("plan", "deck"))
    args = parser.parse_args(argv)
    model = TalkPlan if args.which == "plan" else Deck
    print(json.dumps(model.model_json_schema(), indent=2))
    return 0


def _formats_command(argv: Sequence[str]) -> int:
    from talkgenerator.schema.presentation_schema_types import schemas

    parser = argparse.ArgumentParser(
        prog="talkgenerator formats",
        description="The talk formats; with --details, the slides a plan for one can have (kinds, texts, recipes).",
    )
    parser.add_argument("--details", action="store_true", help="the slides a plan for the format can have")
    parser.add_argument("--format", dest="schema", default="default", choices=schemas.names(), help="the format")
    parser.add_argument("--json", action="store_true", help="as JSON instead of Markdown")
    args = parser.parse_args(argv)

    if args.details:
        text = json.dumps(catalog(args.schema), indent=2) if args.json else catalog_markdown(args.schema)
    elif args.json:
        text = json.dumps(
            [{"format": name, "description": FORMATS.get(name, "")} for name in schemas.names()], indent=2
        )
    else:
        text = "\n".join(f"{name}: {FORMATS.get(name, '')}" for name in schemas.names())
    _print(text)
    return 0


def _print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # a console that can't show every character
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
