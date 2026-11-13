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
from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from talkgenerator import names, settings
from talkgenerator.checks.deck import check_deck
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import themes
from talkgenerator.images import context as image_context
from talkgenerator.images import generation as image_generation
from talkgenerator.images import licenses, vision
from talkgenerator.images.generation import ImageBudget
from talkgenerator.images.generators import ImageGenerator, generator_from_spec
from talkgenerator.llm.base import TextProvider
from talkgenerator.llm.ledger import Ledger
from talkgenerator.models.deck import Deck, ImageElement, TextElement
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, PRESENTER_JOB, PRESENTER_NAME, TALK_TITLE, Recipe, TextField
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
    "pitch": "A startup pitch to investors: the problem, the solution, the market (TAM, SAM and SOM), the business "
    "model, the traction, the competition, the team, the roadmap and the ask, each a part of its arc, in that order",
    "academic": "A talk at an academic conference, with affiliations on its title slide: the motivation (the problem "
    "the research is about), the outline, related work, the method, the results (with p-values), the limitations, "
    "future work, the acknowledgements and the references, each a part of its arc, in that order",
    "corporate": "A company's all-hands meeting or quarterly business review: the agenda, the KPIs against their "
    "targets, the quarter's wins, the roadmap, an org change, the synergies and the ask of everyone, each a part of "
    "its arc, in that order",
    "keynote": "A product keynote on a big stage: a big opening statement, the one idea, the reveal of the product, "
    "its features, a live demo, the price, the 'one more thing' and a closing line, each a part of its arc, in that "
    "order",
    "infomercial": "A late-night TV infomercial for a gadget made of the topic: the everyday problem, the gadget, its "
    "demonstration, testimonials, the fine print, the price, 'But wait, there's more!' and the call to order now, each "
    "a part of its arc, in that order",
    "documentary": "A nature documentary about the topic as a wild species, in a hushed voice: the opening shot, its "
    "habitat, its behaviour, a rare sighting, its rituals, the dangers it faces and a closing reflection, each a part "
    "of its arc, in that order",
    "court": "A court case in which the topic stands trial for a harmless crime: the charges, the evidence, a "
    "witness, the alibi, an objection, the closing argument and the verdict, each a part of its arc, in that order",
    "museum": "A guided museum tour of a collection about the topic: the welcome and the house rules, a masterpiece, "
    "the artist, the eras, an artefact and the gift shop, each a part of its arc, in that order",
    "wedding": "A wedding toast by the best man or the maid of honour, for their best friend, who marries the topic: "
    "who the speaker is, how the couple met, an embarrassing story, why they're perfect together, marriage advice and "
    "the toast, each a part of its arc, in that order",
    "book_report": "A school book report on a book about the topic: the book, its author, the main characters, what "
    "happens, the favourite part, the moral of the story and the rating, each a part of its arc, in that order",
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
    "venn": ("venn-diagram",),
    "matrix": ("2x2-matrix",),
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
    a copyright-free default for a kind that has none of its default recipes. (A format beyond the TED-like talks,
    such as a pitch, borrows one only for a kind it has no recipes of: its own are its kinds' defaults.)"""
    from talkgenerator.schema.slide_schemas import slide_generators  # every registered slide generator

    own = _choices(schema.slide_generators)
    everywhere = _choices(slide_generators)
    borrowed = []
    for kind, preferred in _DEFAULT_RECIPES.items():
        if any(choice.id in preferred and choice.recipe.kind == kind for choice in own):
            continue
        if schema.format is not None and any(choice.recipe.kind == kind for choice in own):
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
    choices: Sequence[RecipeChoice],
    slide: SlidePlan,
    language: str = "en",
    unservable: Collection[SlideGeneratorData] = frozenset(),
) -> tuple[RecipeChoice | None, list[str]]:
    """The recipe a planned slide gets (None if it can't be made), and warnings about the one it asked for. In a
    talk in another language than English, that's never one that finds its texts itself: they'd be English; and
    never one whose images the license policy allows no source for (unservable: their slide generators)."""
    if slide.kind not in PLANNABLE_KINDS:
        return None, [f"there's no slide kind {slide.kind!r}; the kinds are {', '.join(PLANNABLE_KINDS)}"]
    warnings = []
    choices = [choice for choice in choices if choice.generator not in unservable] if unservable else choices
    if slide.recipe:
        found = next((choice for choice in choices if choice.id == recipe_id(slide.recipe)), None)
        if found is None and any(choice.id == recipe_id(slide.recipe) for choice in _choices(unservable)):
            warnings.append(
                f"the images of recipe {slide.recipe!r} are fair use, or of another license class the talk's license "
                f"policy doesn't allow: the default one for {slide.kind} was used"
            )
        elif found is None:
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
        elif slot in recipe.omit:
            warnings.append(f"this recipe shows no {slot}")
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
    parallel: bool | int = True,
    debug_notes: bool = False,
    theme: str | None = None,
    name_styles: Sequence[str] | str | None = None,
    license_policy: str | Sequence[str] | None = None,
    image_generator: ImageGenerator | str | None = None,
    image_budget: ImageBudget | None = None,
    vision_pick: bool | str | TextProvider | None = None,
) -> dict[str, Any]:
    """Realize a plan, save it as a PowerPoint (at output, or under an unused name in output_folder), with the deck's
    JSON (<name>.deck.json) and a contact sheet of its images (<name>.images.png) next to it, and return the report:
    what came out as planned, what didn't and why, what every image was searched with, and the checks.

    With local_images (a folder), image "queries" that name image files there put those files on the slides. Nothing
    is saved over plan_path, the plan's own file. theme (or else the plan's own) is its look, as --theme takes it.

    The presenter is the one given, or else the plan's presenter_name (when it will do: see
    talkgenerator.names.clean), or else a name talkgenerator makes up, in one of name_styles (see
    talkgenerator.names.catalog).

    license_policy is the license classes its images may have (see talkgenerator.images.licenses): the format's,
    without one.

    image_generator generates pictures for the images that prefer one (from the plan's prompts, or else their
    queries) and for images whose search finds nothing, a few at most (image_budget): see generate_presentation.
    Without one, TALKGENERATOR_IMAGE_GENERATOR's, if it names one. The report says what they cost.

    vision_pick has a vision model pick every image among a few candidates (or none: the finder's stays), in one
    request: a model's spec (such as "anthropic:claude-haiku-5-5"), a provider, or True for OpenRouter's free models
    that read pictures (see talkgenerator.images.vision). Off without one. The report says what it made of them."""
    from talkgenerator import generator  # (here: the generator module imports the schemas)

    schema = generator.get_schema(schema_name)
    policy = licenses.policy(license_policy if license_policy is not None else schema.license_policy)
    rng = random_util.Rng(int_seed)
    # The look first, for the images to go with its colours (it has a random stream of its own: the same either way)
    look = theme or plan.theme or settings.theme()
    chosen_theme = themes.pick(themes.RANDOM if look == themes.CHAOS else look, rng.child("theme"))
    chosen_styles = names.styles(name_styles)
    notes: list[str] = []
    named = presenter or names.clean(plan.presenter_name)  # (a name given, which may be someone's: not made up)
    if not presenter:
        presenter = names.clean(plan.presenter_name)
        if plan.presenter_name.strip() and presenter is None:
            notes.append(
                f"the presenter_name {plan.presenter_name!r} isn't a name talkgenerator puts on a title slide (one of "
                f"at most {PRESENTER_NAME.max_length} characters, with letters, spaces, dots, apostrophes and "
                "hyphens, and no placeholder or real person's name), so it made one up"
            )
        presenter = presenter or names.from_pack([plan.topic], chosen_styles, rng)

    ledger = Ledger()
    generation = image_generation.for_talk(image_generator, image_budget, policy, ledger, [plan.topic], presenter)
    # (a plan's slides are planned: their image queries say what a picture is to show)
    picking = vision.for_talk(vision_pick, None, ledger, None, rng.child("vision pick"), named, planned=True)
    images = image_context.ImageContext(
        policy, generator.palette(chosen_theme), schema.looks, generation, vision=picking
    )
    with image_context.for_talk(images):
        choices = recipes_of(schema)
        unservable = schema.unservable()
        chosen = [choose_recipe(choices, slide, plan.language, unservable) for slide in plan.slides]
        recipes = [(choice.generator, choice.recipe) if choice else None for choice, _ in chosen]
        # The recipes as chosen, which the slides' notes then name
        resolved = tuple(
            slide.model_copy(update={"recipe": choice.id}) if choice else slide
            for slide, (choice, _) in zip(plan.slides, chosen, strict=True)
        )
        slide_deck, outcomes = schema.realize_plan(
            plan.model_copy(update={"slides": resolved}), recipes, presenter, rng, local_images, parallel
        )
    slide_deck.theme = chosen_theme
    slide_deck.style_chaos = 1.0 if look == themes.CHAOS else 0.0
    slide_deck.license_policy = policy.name
    slide_deck.usage = ledger.total()
    picked_by = ledger.vision_models()
    slide_deck.vision_model = picked_by[-1] if picked_by else None
    if generation is not None or picking is not None:
        logger.info(ledger.summary())
    deck = slide_deck.to_deck(schema_name=schema_name)

    name = file_name or _file_name(plan.title or plan.topic)
    pptx = Path(_save(schema.render(slide_deck, debug_notes), output, Path(output_folder), name))
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
        "theme": deck.theme,
        "license_policy": deck.license_policy,
        "seed": rng.root_seed,
        "summary": {
            "deck_slides": deck.counted(),  # the title slide too (not the closer after the slides: D76)
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
    if generation is not None:
        usage = deck.usage
        report["generated_images"] = {
            "generator": generation.generator.id,
            "generated": usage.images,  # (made now: the ones the cache had cost nothing)
            "on_slides": sum(
                1 for slide in deck.slides for image in slide.images() if image.license_class == "generated"
            ),
            "failed": usage.failed_images,
            "cost_usd": round(usage.image_cost_usd, 4),
            "estimate": str(generation.estimate()),
        }
    if picking is not None:
        verdicts = [image.vision for slide in deck.slides for image in slide.images() if image.vision is not None]
        report["vision_pick"] = {
            "model": deck.vision_model or picking.id,
            "requests": deck.usage.vision_requests,
            **{verdict: verdicts.count(verdict) for verdict in ("picked", "kept", "refused")},
        }
    for text_field in (TALK_TITLE, PRESENTER_JOB):
        if len(" ".join(getattr(plan, text_field.name).split())) > length_limit(text_field):
            # (a job is cut where a phrase of it ends, or left out: D81)
            done = "shortened where a phrase ends, or left out" if text_field.phrases else "cut off"
            notes.append(f"the {text_field.name} has more than {text_field.max_length} characters, so it was {done}")
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
                "license": element.image.license or element.image.license_class,
                "look": element.image.look,
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

    schema = generator.get_schema(schema_name)
    choices = recipes_of(schema)
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
    data: dict[str, Any] = {"format": schema_name, "description": FORMATS.get(schema_name, ""), "kinds": kinds}
    talk_format = schema.format
    if talk_format is not None:
        # What a format beyond the TED-like talks is (see talkgenerator.schema.formats): what its titles and its
        # presenter's job are like, and its arc, each part with the fewest and the most slides it has, and its recipes
        data["titles"], data["presenter_job"] = talk_format.title_hint, talk_format.job_hint
    if talk_format is not None and talk_format.arc is not None:
        data["arc"] = [
            {
                "part": part.name,
                "slides": [part.fewest, part.most],
                "recipes": sorted(choice.id for choice in choices if part.name in choice.generator.get_tags()),
            }
            for part in talk_format.arc.parts
        ]
    return data


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
    looks = _looks(recipe)
    if looks:
        entry["image_looks"] = looks
    if recipe.omit:
        entry["leaves_out"] = sorted(recipe.omit)
    if recipe.texts_from:
        entry["finds_itself"] = sorted(recipe.texts_from)
    return entry


def _looks(recipe: Recipe) -> dict[str, str]:
    """The look of each of a recipe's images, as its image slot asks for it (see talkgenerator.images.profiles): what
    the images will look like, and where they come from. (Of a mix of slots, each slide's dice picking one, as a
    statement's backdrop: their looks, "calm-backdrop or backdrop".)"""
    from talkgenerator.images.slots import ImageSlot
    from talkgenerator.util.generator_util import CombinedGenerator

    def look(source: ImageSlot) -> str:
        return (
            source.aesthetic
            + "".join(f", else {backup}" for backup in source.backups)
            + (" (or generated, from its prompt, with an image generator set up)" if source.generate else "")
        )

    looks = {}
    for name, source in recipe.slots():
        if isinstance(source, ImageSlot):
            looks[name] = look(source)
        elif isinstance(source, CombinedGenerator) and all(isinstance(each, ImageSlot) for each in source.choices):
            looks[name] = " or ".join(
                dict.fromkeys(look(each) for each in source.choices if isinstance(each, ImageSlot))
            )
    return looks


def catalog_markdown(schema_name: str = "default") -> str:
    """The catalog as Markdown, for people and for the Skill's reference (skill/.../references/slides.md)."""
    data = catalog(schema_name)
    article = "an" if schema_name[:1] in "aeiou" else "a"  # ("an `academic` talk", "an `infomercial` talk")
    lines = [
        f"# The slides of {article} `{schema_name}` talk",
        "",
        f"{data['description']}.",
        "",
        "Every talk starts with a title slide, made from the plan's `title`, `presenter_job` and `presenter_name` "
        "(or the name given to render, or one talkgenerator makes up). The plan's `slides` come after it, each of "
        "one of the kinds below, and the talk ends with a closer of talkgenerator's own after them, which says the "
        'talk is over in its language and format ("Thank you!" and "Questions?", "Let\'s talk" for a pitch): '
        "a plan needs no slide for that. A slide's `recipe` "
        "picks its look and its image sources, and makes the slide the classic way when it can't be made as "
        "planned; without one, a slide gets its kind's default recipe. The look of a recipe's images (its "
        "aesthetic profile) says what they look like and where they come from: `photo` is stock photos, `vintage` "
        "old photographs in black and white or sepia, `meme-chaos` Reddit's weird pictures, ShitpostBot's images, "
        "gifs and memes, and so on (`talkgenerator formats --looks` lists them all).",
        "",
        f"Made by `talkgenerator formats --details --format {schema_name}`.",
    ]
    if "titles" in data:
        lines += [
            "",
            f"A plan's `title` is {data['titles']}, and its `presenter_job` is {data['presenter_job']}.",
        ]
    if "arc" in data:
        lines += [
            "",
            "## The arc",
            "",
            "A talk of this format goes through these parts, in this order, each with the slides of its recipes: a "
            "talk too short for all of them keeps the most important ones, and a long one gives some of them more "
            "slides, with the format's other slides in between. A plan reads as one of this format when its slides "
            "follow the arc (talkgenerator doesn't hold a plan to it).",
            "",
            "| Part | Slides | Recipes |",
            "| --- | --- | --- |",
        ]
        for part in data["arc"]:
            fewest, most = part["slides"]
            count = str(fewest) if fewest == most else f"{fewest} to {most}"
            recipes = ", ".join(f"`{recipe}`" for recipe in part["recipes"])
            lines.append(f"| `{part['part']}` | {count} | {recipes} |")
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
            looks = recipe.get("image_looks", {})
            if looks:
                notes.append("images: " + ", ".join(f"`{name}` {look}" for name, look in looks.items()))
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
    parser.add_argument(
        "--presenter",
        help="the presenter's name, for the title slide (default: the plan's presenter_name, or else a made-up one)",
    )
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
    parser.add_argument(
        "--theme",
        choices=themes.choices(),
        help="the look: random, classic (the 2019 template), a theme family, or chaos (default: the plan's own, or "
        "else TALKGENERATOR_THEME's, or random)",
    )
    parser.add_argument(
        "--license_policy",
        help="the license classes the images may have: all, open (no fair use: no memes, gifs or Reddit's posts), or "
        "classes separated by commas (default: the format's: open for ted, else all)",
    )
    parser.add_argument(
        "--image_generator",
        help="generates pictures for the images that prefer one (from the plan's prompts, or else their queries) and "
        "for images whose search finds nothing: openai[:<model>], openrouter[:<model>], gemini[:<model>], "
        "flux[:<model>], comfyui, automatic1111 or none; they cost money, on your own key (default: "
        "TALKGENERATOR_IMAGE_GENERATOR's, or else none)",
    )
    parser.add_argument(
        "--generated_images",
        type=int,
        help="how many pictures a plan generates at most (default: TALKGENERATOR_GENERATED_IMAGES's, or else 3)",
    )
    parser.add_argument(
        "--vision_pick",
        nargs="?",
        const="on",
        help="have a vision model pick every image among a few candidates, in one request: alone or 'on' for "
        "OpenRouter's free models that read pictures, or a model, as provider:model, such as "
        "anthropic:claude-haiku-5-5 (default: none)",
    )
    parser.add_argument("--open", action="store_true", help="open the PowerPoint afterwards")
    parser.add_argument("--verbose", "-v", action="store_true", help="show the generator's logs (on stderr)")
    args = parser.parse_args(argv)
    if args.license_policy is not None:
        try:
            licenses.policy(args.license_policy)
        except ValueError as error:
            parser.error(str(error))
    if args.image_generator is not None:
        try:
            generator_from_spec(args.image_generator)
        except ValueError as error:
            parser.error(str(error))
    if args.vision_pick is not None:
        try:
            vision.check_spec(args.vision_pick)
        except ValueError as error:
            parser.error(str(error))
    budget = None
    if args.generated_images is not None:
        budget = ImageBudget(max(0, args.generated_images), settings.image_cost_limit())

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
        problem = plan_error(plan, args.schema, args.theme)
        if problem is not None:
            reports.append({"plan": path, "error": problem})
            continue
        report = render_plan(
            plan,
            schema_name=args.schema or plan.format or "default",
            presenter=args.presenter,
            int_seed=args.int_seed,
            output=args.output,
            output_folder=args.output_folder,
            file_name=Path(path).stem,
            save_json=args.save_json,
            contact_sheet=args.contact_sheet,
            plan_path=Path(path),
            local_images=Path(path).resolve().parent,
            theme=args.theme,
            license_policy=args.license_policy,
            image_generator=args.image_generator,
            image_budget=budget,
            vision_pick=args.vision_pick,
        )
        reports.append({"plan": path, **report})
        if args.open:
            generator._open_file(os.path.realpath(report["pptx"]))

    # ASCII only: the report is for programs too, and this way no console encoding mangles it
    print(json.dumps(reports[0] if len(reports) == 1 else reports, indent=2))
    return 2 if any("error" in report for report in reports) else 0


def plan_error(plan: TalkPlan, schema_name: str | None = None, theme: str | None = None) -> str | None:
    """Why a plan can't be rendered: a format, theme or language talkgenerator doesn't know (None if it can be).
    schema_name and theme are what's asked for instead of the plan's own."""
    from talkgenerator.schema.presentation_schema_types import schemas

    return (
        unknown_choice("format", schema_name or plan.format or "default", schemas.names())
        or unknown_choice("theme", theme or plan.theme or settings.theme(), themes.choices())
        or unknown_choice("language", plan.language, list(languages.LANGUAGES))
    )


def unknown_choice(what: str, value: str, choices: Sequence[str]) -> str | None:
    """What's wrong with a value that's none of the choices, such as a theme that doesn't exist (None if it's fine)."""
    return None if value in choices else f"there's no {what} {value!r}; the {what}s are {', '.join(choices)}"


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
    parser.add_argument(
        "--looks", action="store_true", help="the looks images can be found in (aesthetic profiles and flavour packs)"
    )
    parser.add_argument(
        "--licenses", action="store_true", help="the license policies, and the license classes they pick from"
    )
    parser.add_argument(
        "--memes", action="store_true", help="the meme templates a meme slide can have, and what each caption says"
    )
    parser.add_argument(
        "--generators",
        action="store_true",
        help="the image generators' models and list prices, and the generator that's set up (if any)",
    )
    parser.add_argument("--format", dest="schema", default="default", choices=schemas.names(), help="the format")
    parser.add_argument("--json", action="store_true", help="as JSON instead of Markdown")
    args = parser.parse_args(argv)

    if args.memes:
        entries = meme_catalog()
        if args.json:
            text = json.dumps(entries, indent=2)
        else:
            text = "\n".join(
                f"{entry['name']}: {entry['about']}\n"
                + "\n".join(f"  text_{number}: {says}" for number, says in enumerate(entry["captions"], 1))
                for entry in entries
            )
    elif args.generators:
        from talkgenerator.images.generators import prices

        models = prices.catalog()
        spec = settings.image_generator_spec()
        if args.json:
            text = json.dumps({"set_up": spec, "checked": prices.config().get("checked"), "models": models}, indent=2)
        else:
            lines = [f"Set up: {spec} (TALKGENERATOR_IMAGE_GENERATOR; prices checked {prices.config().get('checked')})"]
            for entry in models:
                price = entry["price_usd"]
                shown = (
                    ", ".join(f"{quality} ${value}" for quality, value in price.items())
                    if isinstance(price, dict)
                    else f"${price}"
                )
                notes = (" (the default)" if entry["default"] else "") + (
                    f" (retiring {entry['retiring']})" if entry.get("retiring") else ""
                )
                lines.append(f"{entry['provider']}:{entry['model']}: {shown} a picture{notes}")
            lines.append("comfyui, automatic1111: servers of your own, for nothing")
            text = "\n".join(lines)
    elif args.looks or args.licenses:
        from talkgenerator.images import licenses as license_policies
        from talkgenerator.images import profiles

        entries = profiles.catalog() if args.looks else license_policies.catalog()
        if args.json:
            text = json.dumps(entries, indent=2)
        else:
            text = "\n".join(
                f"{entry['name']}: {entry['description']}"
                + (" (a flavour pack)" if entry.get("kind") == "flavour pack" else "")
                for entry in entries
            )
    elif args.details:
        text = json.dumps(catalog(args.schema), indent=2) if args.json else catalog_markdown(args.schema)
    elif args.json:
        text = json.dumps(
            [
                {
                    "format": name,
                    "description": FORMATS.get(name, ""),
                    "license_policy": schemas.get(name).license_policy,
                }
                for name in schemas.names()
            ],
            indent=2,
        )
    else:
        text = "\n".join(
            f"{name}: {FORMATS.get(name, '')} (license policy: {schemas.get(name).license_policy})"
            for name in schemas.names()
        )
    _print(text)
    return 0


def meme_catalog() -> list[dict[str, Any]]:
    """The meme templates a meme slide can have (talkgenerator.sources.memes), for agents writing plans: the name its
    template_query gives, what it shows, and what each of its captions says (text_1, text_2...)."""
    from talkgenerator.sources import memes

    return [
        {"name": template.name, "about": template.about, "captions": [box.says for box in template.written()]}
        for template in memes.templates().values()
    ]


def _print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # a console that can't show every character
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
