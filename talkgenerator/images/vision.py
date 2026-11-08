"""The vision pick (docs/v5-plan.md, 10.3, item 4): a vision model looks at a few candidates for every picture of a
talk, side by side, and picks the one that shows what its slide asked for, or none of them.

A talk has one only when it's asked for (generate_presentation's and stream_talk's vision_pick, --vision_pick), and
only its planned slides take part (by a language model, or a plan), as their image queries say what a picture is to
show. Then:

1. The image finder keeps the runners-up of every picture it finds for a planned slide: the other candidates of the
   sources that found it, best first, taken from each source in turn (talkgenerator.images.finder.RunnersUp). That
   draws nothing from the talk's dice, so a talk with a vision pick finds the same pictures as a talk without one,
   before the pick.
2. As each slide is settled, the thumbnails of its pictures' candidates are fetched, in the background.
3. Once the last slide is settled, a contact sheet shows every picture's candidates in a row of their own, one row
   under another, with what the picture is to show beside it: the finder's picture and up to three runners-up, in an
   order the talk's seed shuffles (so a model can't favour the finder's by its place), each labelled with its row's
   number and a letter. One request, with the sheet and what each slide says, asks the vision model what each row's
   candidates show, and which one comes closest to what it asked for, or none: one request a talk, however many
   pictures it has (the first ten).
4. A picked runner-up takes the finder's picture's place once it passes the finder's checks (downloaded, or probed
   while the talk streams; not on another slide, nor nearly the same as a picture there), and a talk that streams
   hands the changed slides over again (slide.updated). A row it refused or didn't answer keeps the finder's picture,
   and so does every row when the request fails, is turned down or takes too long, or the talk's budget doesn't
   allow it.

Every picture it looked at says what it made of it (ImageData.vision, the deck's ImageAsset.vision): "picked", "kept"
or "refused". Its request is the talk's: in its ledger and budget (the deck's usage counts it among its requests, and
as a vision request), never with the presenter's name, and a recorded answer replays (talkgenerator.llm.replay): the
sheet is named by its candidates, so the same candidates make the same request, and the same answer the same deck.
"""

from __future__ import annotations

import contextvars
import copy
import hashlib
import io
import logging
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent import futures
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import analysis, profiles
from talkgenerator.llm.base import BudgetExceeded, ImagePart, ProviderError, TextProvider, TextRequest, TextResponse
from talkgenerator.llm.ledger import VISION, Budget, Ledger, LedgerEntry, MeteredProvider
from talkgenerator.llm.sdk import parse_json
from talkgenerator.models.deck import DECORATION, TextElement
from talkgenerator.models.usage import Usage
from talkgenerator.util import image_util, os_util, random_util

if TYPE_CHECKING:
    from talkgenerator.slide.slide_deck import SlideDeck
    from talkgenerator.slide.slides import Slide

logger = logging.getLogger("talkgenerator")

PURPOSE: Final = VISION  # (the request's purpose, in the talk's ledger)
CANDIDATES: Final = 4  # in a row: the finder's picture, and up to three runners-up
MAX_ROWS: Final = 10  # pictures a talk's sheet shows at most (the first ones, in the order of the slides)
# OpenRouter's free models that read pictures, in the order to try them, and how hard they think first: not at all, as
# they say what each row's candidates show before they pick. (Measured on 2026-11-08, on the contact sheets of six
# talks, 25 rows: Nemotron picked a picture that shows what was searched for in 16, dots-3 in 16, against the finder's
# 13, in 2 to 9 seconds; thinking first, Nemotron took 8 to 44 seconds for 17, and over a minute without a cap. The
# free router sent the sheet to a model that couldn't tell a red circle from a blue square, and Gemma 4's free
# endpoints turned the request's parameters down.)
FREE_MODELS: Final = ("nvidia/nemotron-3.5-super-vl:free", "dots-studio/dots-3-note-preview:free")
FREE_EFFORT: Final = "none"
# The looks whose pictures it doesn't pick: moving ones (a still of a gif shows the least of it), InspiroBot's posters
# (no thumbnails), meme templates (a recipe fixes which) and flags (a country's is the one)
SKIPPED_LOOKS: Final = frozenset({"gifs", "inspirobot", "meme-templates", "country"})
WAIT_SECONDS: Final = 30.0  # the longest a talk waits for the answer before it does without
# The sheet: one row under another (in two columns, models paired rows with the wrong queries), each with its number
# and what it asks for on its left, and its candidates in cells of 4:3 (a thumbnail fits in one, on gray)
CELL: Final = (200, 150)
GAP: Final = 6
LABEL_WIDTH: Final = 230
_BACKGROUND: Final = (255, 255, 255)
_EMPTY: Final = (232, 232, 232)
_FONT: Final = "data/fonts/AtkinsonHyperlegible-Bold.ttf"
_TEXT_FONT: Final = "data/fonts/AtkinsonHyperlegible-Regular.ttf"
_LETTERS: Final = "ABCD"
_THREADS: Final = 16  # (thumbnails, fetched as the slides are settled: about forty a talk)
# What the model is told (what it picks among, and how to answer), and what a row says
SYSTEM: Final = (
    "You pick pictures for the slides of a funny talk. You're shown a contact sheet of candidate pictures, one row for "
    "each picture a slide needs, and you say which candidate of each row shows what that slide's picture is meant to "
    "show."
)
_INSTRUCTIONS: Final = (
    "The contact sheet has one row for each picture below, one under another: on the left of each row, its number and "
    'what it asks for, and then its candidates, each labelled with the row\'s number and a letter (such as "3B").\n\n'
    "For each row, say in a few words what each of its candidates shows, and then pick the candidate that comes "
    "closest to what the row asks for: its subject first (the thing, animal, person or place), then the rest of it, "
    "and how well it goes with what the slide says. A candidate that shows the subject beats none, even without the "
    "rest; between two that come as close, pick the clearer picture, without large text, watermarks or collages. "
    'Answer "none" for a row only when none of its candidates shows its subject at all.\n\nThe rows:\n'
)


@dataclass
class _Row:
    """A picture of a settled slide, and the candidates for its place, in the order the sheet shows them (the
    finder's picture among them), with their thumbnails."""

    slide_nr: int
    slide: Slide
    image: ImageData  # the finder's picture, on the slide
    candidates: list[ImageData]
    thumbnails: list[Image.Image]
    says: str  # what the slide says, as the model is told it
    wants: str = ""  # what the picture is to show, as the model is told it (on the sheet too)

    @property
    def letters(self) -> str:
        return _LETTERS[: len(self.candidates)]


class VisionPick:
    """A talk's vision pick: the model it asks, the talk's ledger and budget (which the request goes into and keeps
    to), and its slides with pictures to pick, as they're settled (`settled`). `finish`, once the last one is, asks the
    model and puts its picks in their places; `close` stops (for a talk that stopped)."""

    def __init__(
        self,
        provider: TextProvider,
        rng: random_util.Rng,
        presenter: str | None = None,
        ledger: Ledger | None = None,
        budget: Budget | None = None,
    ) -> None:
        self.provider = provider
        self.rng = rng
        self.presenter = presenter
        self.ledger = ledger if ledger is not None else Ledger()
        self.budget = budget or Budget()
        self._slides: dict[int, Slide] = {}  # the settled slides with pictures to pick, by slide number
        self._closed = False
        self._lock = threading.Lock()
        self._pool: ThreadPoolExecutor | None = None
        self._fetching: list[Future[Any]] = []

    @property
    def id(self) -> str:
        return self.provider.id

    def settled(self, slide_nr: int, slide: Slide) -> None:
        """Note a settled slide, if it has pictures to pick, and start fetching their candidates' thumbnails."""
        pictures = _pictures(slide)
        if not pictures:
            return
        with self._lock:
            if self._closed:
                return
            self._slides[slide_nr] = slide
        for picture in pictures:
            # (one more than the sheet shows, for one that can't be had; the sheet fetches more if it needs them)
            for candidate in (picture, *_runners_up(picture)[:CANDIDATES]):
                if candidate.thumbnail_url:
                    run = contextvars.copy_context().run  # (fetched as this talk fetches)
                    self._fetching.append(self._executor().submit(run, analysis.thumbnail, candidate.thumbnail_url))

    def finish(self, slide_deck: SlideDeck, cancelled: threading.Event | None = None) -> bool:
        """Ask the model to pick among the candidates of the settled slides' pictures, and put its picks in their
        places, handing over the slides that changed (slide_deck.slide_updated): whether the talk goes on (False if
        it was cancelled meanwhile, looked at four times a second)."""
        try:
            with self._lock:
                if self._closed:
                    return True
                fetching = list(self._fetching)
            futures.wait(fetching)  # (a thumbnail that can't be had is None: they don't fail)
            # (the name given for the presenter, which may be someone's: a made-up one was the model's own, and a
            # pun on the topic, whose words the slides need)
            rows = self._rows(slide_deck, self.presenter)
            if not rows:
                return True
            sheet = contact_sheet(rows)
            request = picking_request(rows, sheet, self.presenter)
            logger.info("Asking %s to pick %d pictures among their candidates", self.provider.id, len(rows))
            response = self._ask(request, cancelled)
            if cancelled is not None and cancelled.is_set():
                return False
            if response is None:
                return True
            picks = read_answer(response, rows)
            self._put_in_place(rows, picks, slide_deck)
            return True
        finally:
            self._forget_runners_up()
            self._shut_down()

    def close(self) -> None:
        """Stop: no request goes out, and an answer that's still coming isn't used (a talk nobody wants anymore)."""
        with self._lock:
            self._closed = True
        self._forget_runners_up()
        self._shut_down()

    # ASKING

    def _rows(self, slide_deck: SlideDeck, presenter: str | None) -> list[_Row]:
        """A row for every picture of the settled slides (in their order, and the order of their pictures) that has
        candidates the sheet can show besides it: up to MAX_ROWS of them."""
        shown = _deck_images(slide_deck)
        rows: list[_Row] = []
        with self._lock:
            settled = sorted(self._slides.items())
        for slide_nr, slide in settled:
            for index, picture in enumerate(_pictures(slide)):
                if len(rows) >= MAX_ROWS:
                    logger.info("The vision pick shows the first %d pictures only", MAX_ROWS)
                    return rows
                row = self._row(slide_nr, slide, index, picture, shown, presenter)
                if row is not None:
                    rows.append(row)
        return rows

    def _row(
        self,
        slide_nr: int,
        slide: Slide,
        index: int,
        picture: ImageData,
        shown: Sequence[ImageData],
        presenter: str | None,
    ) -> _Row | None:
        """The picture's row: it and the runners-up the sheet can show (those with a thumbnail, not on a slide nor
        nearly, and with the picture's look, if it prefers something), in an order the talk's seed shuffles. None
        when it has none of them, or no thumbnail itself."""
        runners_up = picture.runners_up
        own = _picture(picture.thumbnail_url)
        if runners_up is None or own is None:
            return None
        look = profiles.PROFILES.get(runners_up.look)
        prefers = look.prefers if look is not None else None
        candidates, thumbnails = [picture], [own]
        for candidate in runners_up.images:
            if len(candidates) >= CANDIDATES:
                break
            if any(candidate == other for other in (*shown, *candidates)):
                continue
            thumbnail = _picture(candidate.thumbnail_url)
            if thumbnail is None or candidate.thumbnail_url is None:
                continue
            seen = analysis.look_at(candidate.thumbnail_url, runners_up.area)
            if any(analysis.near_duplicates(seen, other.analysis) for other in (*shown, *candidates)):
                continue
            if prefers is not None and not prefers.met_by(seen):
                continue
            candidates.append(candidate)
            thumbnails.append(thumbnail)
        if len(candidates) < 2:
            return None
        order = list(range(len(candidates)))
        with random_util.use(self.rng.child("row", slide_nr, index)):
            random_util.shuffle(order)
        return _Row(
            slide_nr,
            slide,
            picture,
            [candidates[place] for place in order],
            [thumbnails[place] for place in order],
            _what_it_says(slide, presenter),
            _what_it_shows(picture, presenter),
        )

    def _ask(self, request: TextRequest, cancelled: threading.Event | None) -> TextResponse | None:
        """The model's answer, asked on a thread of its own (so a cancelled talk needn't wait for it), once the talk's
        budget allows it: None when there's none (an error, a refusal, the budget), or it takes longer than
        WAIT_SECONDS. The talk's ledger gets the request when its answer is in, or as a failed one when the talk
        stops waiting for it (a free tier counts it either way)."""
        try:
            for model in self.provider.possible_models():
                self.budget.check(self.ledger, model, request, self.provider.max_output_tokens(request))
        except BudgetExceeded as exceeded:
            logger.info("The talk's budget doesn't allow the vision pick (%s): the finder's pictures stay", exceeded)
            return None
        answered = Ledger()  # (the request's entry, which joins the talk's if it comes in time)
        metered = MeteredProvider(self.provider, answered)
        answers: list[TextResponse | BaseException] = []
        done = threading.Event()

        def ask() -> None:
            try:
                answers.append(metered.complete(request))
            except BaseException as error:  # (said below, on the talk's thread)
                answers.append(error)
            finally:
                done.set()

        run = contextvars.copy_context().run
        threading.Thread(target=run, args=(ask,), name="vision pick", daemon=True).start()
        start = time.monotonic()
        while not done.wait(0.25):
            gave_up = cancelled is not None and cancelled.is_set()
            if not gave_up and time.monotonic() - start > WAIT_SECONDS:
                logger.warning("The vision pick took over %.0f seconds: the finder's pictures stay", WAIT_SECONDS)
                gave_up = True
            if gave_up:
                usage = Usage(requests=1, vision_requests=1, failed_requests=1)
                waited = time.monotonic() - start
                self.ledger.add(LedgerEntry(self.provider.id, PURPOSE, usage, waited, error="no answer in time"))
                self.close()
                return None
        for entry in answered.entries:
            self.ledger.add(entry)
        with self._lock:
            if self._closed:
                return None
        answer = answers[0]
        if isinstance(answer, ProviderError):
            logger.warning("The vision pick got no answer (%s): the finder's pictures stay", answer)
            return None
        if isinstance(answer, BaseException):
            logger.error("The vision pick crashed: the finder's pictures stay", exc_info=answer)
            return None
        if answer.finish == "refused":
            logger.warning("The vision model turned the pick down: the finder's pictures stay")
            return None
        return answer

    # PUTTING THE PICKS IN PLACE

    def _put_in_place(self, rows: Sequence[_Row], picks: Mapping[int, int | None], slide_deck: SlideDeck) -> None:
        """Note what the model made of every row it answered, and put the runners-up it picked in place of the
        finder's pictures, once they pass their checks (all at once), in the order of the rows: a pick that's on a
        slide already, or nearly, or that won't do, leaves the finder's picture where it is."""
        chosen: dict[int, ImageData] = {}
        for number, row in enumerate(rows, 1):
            if number not in picks:
                continue
            pick = picks[number]
            if pick is None:
                row.image.vision = "refused"
            elif row.candidates[pick] is row.image:
                row.image.vision = "kept"
            else:
                chosen[number] = _as_found(row.candidates[pick], row.image)
        checked = dict(zip(chosen, self._all([_checker(picture) for picture in chosen.values()]), strict=True))
        shown = list(_deck_images(slide_deck))
        changed: set[int] = set()
        for number, picture in chosen.items():
            row = rows[number - 1]
            others = [image for image in shown if image is not row.image]
            if not checked[number]:
                logger.info("The vision pick for slide %d won't do: the finder's picture stays", row.slide_nr + 1)
            elif any(
                picture == other or analysis.near_duplicates(picture.analysis, other.analysis) for other in others
            ):
                logger.info("The vision pick for slide %d is on another slide: the finder's stays", row.slide_nr + 1)
            else:
                picture.vision = "picked"
                row.slide.replace_image(row.image, picture)
                shown = [picture if image is row.image else image for image in shown]
                changed.add(row.slide_nr)
        logger.info(
            "The vision pick: %d picked, %d kept, %d refused, of %d pictures",
            len(changed),
            sum(1 for row in rows if row.image.vision == "kept"),
            sum(1 for row in rows if row.image.vision == "refused"),
            len(rows),
        )
        for slide_nr in sorted(changed):
            slide_deck.slide_updated(slide_nr)

    def _forget_runners_up(self) -> None:
        """Let the runners-up go (they aren't wanted once the pick is done, or the talk stopped)."""
        with self._lock:
            slides, self._slides = list(self._slides.values()), {}
        for slide in slides:
            for picture in _pictures(slide):
                picture.runners_up = None

    # RUNNING THINGS AT ONCE

    def _executor(self) -> ThreadPoolExecutor:
        with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=_THREADS, thread_name_prefix="vision pick")
            return self._pool

    def _all(self, tasks: Sequence[Callable[[], bool]]) -> list[bool]:
        """What the tasks give, in their order: run at once (each in a copy of this context, so images are checked as
        the talk checks them)."""
        if len(tasks) <= 1:
            return [task() for task in tasks]
        futures = [self._executor().submit(contextvars.copy_context().run, task) for task in tasks]
        return [future.result() for future in futures]

    def _shut_down(self) -> None:
        with self._lock:
            pool, self._pool = self._pool, None
            self._fetching = []
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


def _checker(picture: ImageData) -> Callable[[], bool]:
    return lambda: image_util.check_image(picture)


def _as_found(candidate: ImageData, instead_of: ImageData) -> ImageData:
    """A runner-up as the slide gets it: a copy (a source may hand out the same object again), found with the finder's
    picture's query, for its look, with what a look at its thumbnail found."""
    picture = copy.copy(candidate)
    picture.query = instead_of.query
    runners_up = instead_of.runners_up
    picture.look = runners_up.look if runners_up is not None else instead_of.look
    area = runners_up.area if runners_up is not None else None
    picture.analysis = analysis.look_at(candidate.thumbnail_url, area) if candidate.thumbnail_url else None
    picture.runners_up = None
    return picture


def _pictures(slide: Slide) -> list[ImageData]:
    """The slide's pictures that a vision pick may pick (in the order of the slide's images): those with runners-up,
    of a look it picks, but for the stock photos that stand in for generated pictures."""
    standing_in = {id(stand_in) for stand_in, _ in getattr(slide, "wishes", ())}
    return [
        image
        for image in slide.image_store().values()
        if image.runners_up is not None and image.runners_up.look not in SKIPPED_LOOKS and id(image) not in standing_in
    ]


def _runners_up(picture: ImageData) -> tuple[ImageData, ...]:
    return picture.runners_up.images if picture.runners_up is not None else ()


def _deck_images(slide_deck: SlideDeck) -> list[ImageData]:
    """Every picture on the deck's slides so far."""
    return [image for slide in slide_deck.slides() for image in slide.image_store().values()]


def _picture(url: str | None) -> Image.Image | None:
    """The thumbnail at the URL as a picture (in RGB, turned as its camera meant), or None if it can't be had."""
    data = analysis.thumbnail(url) if url else None
    if data is None:
        return None
    try:
        with Image.open(io.BytesIO(data), formats=image_util.accepted_formats()) as opened:
            opened.draft("RGB", (CELL[0] * 2, CELL[1] * 2))  # (a JPEG decodes at a fraction of its size)
            picture = ImageOps.exif_transpose(opened)
            picture.thumbnail(CELL, Image.Resampling.LANCZOS)
            return picture.convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as error:
        logger.debug("Can't show a thumbnail on the contact sheet: %s", error)
        return None


def _what_it_says(slide: Slide, presenter: str | None) -> str:
    """What the slide says (its texts, not its theme's decoration), as the vision model is told it: on one line, at
    most 200 characters, and never with the presenter's name (which goes to no model)."""
    texts = [
        element.text
        for element in slide.to_deck_slide().elements
        if isinstance(element, TextElement) and element.role != DECORATION and element.text.strip()
    ]
    said = " / ".join(" ".join(text.split()) for text in texts)
    said = _without_name(said, presenter)
    return said if len(said) <= 200 else said[:199].rsplit(" ", 1)[0] + "…"


def _what_it_shows(picture: ImageData, presenter: str | None) -> str:
    """What the picture is to show, as the model is told it: what it was searched for, with its slot's intent (never
    with the presenter's name)."""
    query = _without_name(" ".join((picture.query or "").split()), presenter)
    intent = picture.runners_up.intent if picture.runners_up is not None else ""
    return f"{intent}: {query}" if intent and query else query or intent


def _without_name(text: str, presenter: str | None) -> str:
    """The text with "the presenter" where it names them (by their whole name, or a part of it)."""
    if not presenter:
        return text
    parts = [presenter, *(part.strip(".,") for part in presenter.split())]
    for part in parts:
        if len(part) >= 3:
            text = re.sub(rf"\b{re.escape(part)}\b", "the presenter", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe presenter(?:[\s.,]+the presenter)+\b", "the presenter", text)
    return re.sub(r"\b(the|a|an) the presenter\b", r"\1 presenter", text, flags=re.IGNORECASE)


# THE CONTACT SHEET AND THE REQUEST


def contact_sheet(rows: Sequence[_Row]) -> ImagePart:
    """One picture of every row's candidates, one row under another, each with its number and what it asks for on its
    left, and each candidate labelled with its row's number and its letter ("3B"): as JPEG, named by the candidates it
    shows, in their order (so the same candidates make the same request, whatever their thumbnails' bytes)."""
    width = 2 * GAP + LABEL_WIDTH + CANDIDATES * CELL[0] + (CANDIDATES - 1) * GAP
    height = len(rows) * CELL[1] + (len(rows) - 1) * GAP + 2 * GAP
    sheet = Image.new("RGB", (width, height), _BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    number_font, label_font, text_font = _font(34), _font(19), _font(18, _TEXT_FONT)
    for place, row in enumerate(rows):
        left, top = GAP, GAP + place * (CELL[1] + GAP)
        number = str(place + 1)
        draw.text((left, top), number, fill=(0, 0, 0), font=number_font)
        lines = _wrapped(row.wants, text_font, LABEL_WIDTH - 2 * GAP, 5)
        draw.multiline_text((left, top + 42), "\n".join(lines), fill=(40, 40, 40), font=text_font, spacing=3)
        for index, thumbnail in enumerate(row.thumbnails):
            x, y = left + LABEL_WIDTH + index * (CELL[0] + GAP), top
            draw.rectangle((x, y, x + CELL[0] - 1, y + CELL[1] - 1), fill=_EMPTY)
            sheet.paste(thumbnail, (x + (CELL[0] - thumbnail.width) // 2, y + (CELL[1] - thumbnail.height) // 2))
            label = f"{number}{_LETTERS[index]}"
            box = draw.textbbox((x + 5, y + 4), label, font=label_font)
            draw.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=(0, 0, 0))
            draw.text((x + 5, y + 4), label, fill=(255, 255, 255), font=label_font)
    buffer = io.BytesIO()
    sheet.save(buffer, "JPEG", quality=85, optimize=True)
    shown = "\n".join(" ".join(candidate.get_image_url() for candidate in row.candidates) for row in rows)
    name = f"contact sheet {hashlib.sha256(shown.encode('utf-8')).hexdigest()[:16]}"
    return ImagePart(media_type="image/jpeg", data=buffer.getvalue(), width=width, height=height, name=name)


def _font(size: int, file: str = _FONT) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(os_util.to_actual_file(file), size)
    except OSError:  # (Pillow without FreeType: its own font)
        return ImageFont.load_default()


def _wrapped(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int, most: int) -> list[str]:
    """The text in lines that fit the width, at most `most` of them (the last one ending in "…" if it's cut)."""
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(f"{lines[-1]} {word}") <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > most:
        lines = lines[:most]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def picking_request(rows: Sequence[_Row], sheet: ImagePart, presenter: str | None = None) -> TextRequest:
    """The request that shows the model the sheet, and asks it, for each row, what its candidates show (a few words
    each: they make it look before it picks, which a model that doesn't think first needs) and which one to pick, as
    JSON by row number: a letter of the row's, or "none"."""
    lines = []
    for number, row in enumerate(rows, 1):
        wanted = row.wants or _what_it_shows(row.image, presenter)
        said = f' The slide says: "{row.says}"' if row.says else ""
        lines.append(f"{number}. Slide {row.slide_nr + 1}'s picture shows {wanted or 'what the slide says'}.{said}")
    prompt = (
        _INSTRUCTIONS
        + "\n".join(lines)
        + f'\n\nAnswer with JSON only: an object with a key for every row, "1" to "{len(rows)}", each an object with '
        '"shows" (what its candidates show, a few words each) and "pick" (the letter of the candidate you pick, or '
        '"none").'
    )
    schema = {
        "type": "object",
        "properties": {
            str(number): {
                "type": "object",
                "properties": {"shows": {"type": "string"}, "pick": {"type": "string", "enum": [*row.letters, "none"]}},
                "required": ["shows", "pick"],
                "additionalProperties": False,
            }
            for number, row in enumerate(rows, 1)
        },
        "required": [str(number) for number in range(1, len(rows) + 1)],
        "additionalProperties": False,
    }
    return TextRequest.ask(
        PURPOSE, prompt, images=(sheet,), system=SYSTEM, json_schema=schema, max_output_tokens=200 + 80 * len(rows)
    )


_PICK: Final = re.compile(r'"?(\d+)"?\s*[:=]\s*"?(\d*)\s*([A-Da-d]\b|none\b|null\b)', re.IGNORECASE)
_PICK_IN_A_ROW: Final = re.compile(r'"(\d+)"\s*:\s*\{[^{}]*?"pick"\s*:\s*"([^"]*)"', re.IGNORECASE)


def read_answer(response: TextResponse, rows: Sequence[_Row]) -> dict[int, int | None]:
    """What the model picked for the rows it answered, by row number (from 1): the index of a candidate of the row's,
    or None for none of them. A row it gave no letter of the row's (nor "none") isn't in it. A row's answer is its
    "pick" (with what its candidates show), or a letter alone."""
    data = response.data if isinstance(response.data, dict) else parse_json(response.text)
    said: dict[str, Any] = {}
    if isinstance(data, dict):
        said = {str(key).strip(): value for key, value in data.items()}
    elif _PICK_IN_A_ROW.search(response.text):  # (cut off before its end, say: the rows it finished)
        said = {match.group(1): match.group(2) for match in _PICK_IN_A_ROW.finditer(response.text)}
    else:  # (written as "1: B, 2: none" instead)
        said = {match.group(1): match.group(2) + match.group(3) for match in _PICK.finditer(response.text)}
    said = {key: value.get("pick", False) if isinstance(value, dict) else value for key, value in said.items()}
    picks: dict[int, int | None] = {}
    for number, row in enumerate(rows, 1):
        key = next((key for key in (str(number), f"row {number}") if key in said), None)
        if key is None:  # (a row it left out: not answered, which isn't "none")
            continue
        pick = _pick_of(said[key], number, row.letters)
        if pick is not False:
            picks[number] = pick
    return picks


def _pick_of(value: Any, number: int, letters: str) -> int | None | bool:
    """The candidate a value names (its index), None for none, or False when it names neither."""
    if value is None:
        return None
    if not isinstance(value, str):
        return False
    said = value.strip().strip("\"'.").upper()
    if said in ("NONE", "NULL", "NO", "-", ""):
        return None
    said = said.removeprefix(str(number)).strip()
    return letters.index(said) if len(said) == 1 and said in letters else False


# A TALK'S VISION PICK


def provider_for(vision_pick: bool | str | TextProvider | None, talk_model: TextProvider | None) -> TextProvider | None:
    """The model a talk's vision pick asks: the one given (a provider, or a spec such as
    "openrouter:nvidia/nemotron-3.5-super-vl:free" or "anthropic:claude-haiku-5-5"), or for vision_pick=True (or
    "on"), the talk's own language model when it reads pictures (Claude's, OpenAI's, a replayed talk's), and else
    OpenRouter's free models that read pictures (FREE_MODELS). None when it's off (None, False, "none" or "off")."""
    from talkgenerator.llm.openrouter import OpenRouterProvider
    from talkgenerator.llm.providers import NoneProvider, provider_from_spec
    from talkgenerator.llm.replay import ReplayProvider

    if isinstance(vision_pick, TextProvider):
        return None if isinstance(vision_pick, NoneProvider) else vision_pick
    if vision_pick is None or vision_pick is False:
        return None
    if isinstance(vision_pick, str):
        spec = vision_pick.strip()
        if spec.lower() in ("", "none", "off", "false", "no", "0"):
            return None
        if spec.lower() == "openrouter":  # (OpenRouter's free models: its free router sends pictures to weak ones)
            return OpenRouterProvider(FREE_MODELS, effort=FREE_EFFORT)
        if spec.lower() not in ("on", "true", "yes", "1", "default"):
            provider = provider_from_spec(spec)
            return None if isinstance(provider, NoneProvider) else provider
    if talk_model is not None and (talk_model.capabilities.vision or isinstance(talk_model, ReplayProvider)):
        return talk_model
    return OpenRouterProvider(FREE_MODELS, effort=FREE_EFFORT)


def check_spec(vision_pick: str) -> str:
    """The spec, once it's known to turn the vision pick on or off, or to name a provider (a ValueError if not)."""
    provider_for(vision_pick, None)
    return vision_pick


def for_talk(
    vision_pick: bool | str | TextProvider | None,
    talk_model: TextProvider | None,
    ledger: Ledger,
    budget: Budget | None,
    rng: random_util.Rng,
    presenter: str | None = None,
    planned: bool | None = None,
) -> VisionPick | None:
    """The talk's vision pick, asking the model vision_pick says (see provider_for) through the talk's ledger and
    budget, or None: when it's off, and in a talk whose slides aren't planned (a classic talk, without talk_model,
    unless planned says it's a plan's)."""
    provider = provider_for(vision_pick, talk_model)
    if provider is None:
        return None
    if not (planned if planned is not None else talk_model is not None):
        logger.info("Classic talks have no vision pick: %s isn't asked", provider.id)
        return None
    return VisionPick(provider, rng, presenter, ledger, budget)
