"""Offline tests of the vision pick (docs/v5-plan.md, 10.3, item 4; talkgenerator.images.vision): a vision model picks
each picture of a talk's planned slides among a few candidates, side by side on one contact sheet, in one request.
With a fake language model, a fake vision model, fake stock photos and fake thumbnails: nothing goes over the network,
and nothing costs anything.
"""

import hashlib
import io
import json
import os
import random
import threading

import pytest
from PIL import Image, ImageDraw

from talkgenerator import generator
from talkgenerator.checks import benchmark
from talkgenerator.checks.deck import deck_metrics
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.images import analysis, catalog, context, profiles, vision
from talkgenerator.images.profiles import Profile, SourceUse
from talkgenerator.images.slots import ImageSlot
from talkgenerator.llm import prices, providers
from talkgenerator.llm.base import (
    Capabilities,
    ImagePart,
    ProviderUnavailable,
    RateLimited,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.claude import ClaudeProvider
from talkgenerator.llm.ledger import Budget
from talkgenerator.llm.openai_responses import OpenAIProvider
from talkgenerator.llm.openrouter import OpenRouterProvider
from talkgenerator.llm.replay import ReplayProvider, request_key
from talkgenerator.llm.sdk import parse_json
from talkgenerator.models.events import SlideReady, SlideUpdated, TalkFinished
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util import generator_util, image_util, random_util
from talkgenerator.util.generator_util import StaticGenerator
from tests.test_llm_talks import FakeModel

PRESENTER = "Ann Example"
TALK = {"topic": "owls", "presenter": PRESENTER, "int_seed": 3}
SLIDES = 6


def _png(seed: str, size=(160, 120)) -> bytes:
    """A picture of small coloured blocks, its own for every seed (so that no two are near-duplicates: a perceptual
    hash of random blocks this small is random too)."""
    rng = random.Random(seed)
    picture = Image.new("RGB", size)
    draw = ImageDraw.Draw(picture)
    columns, rows = 18, 16
    for row in range(rows):
        for column in range(columns):
            colour = tuple(rng.randrange(256) for _ in range(3))
            box = (
                column * size[0] // columns,
                row * size[1] // rows,
                (column + 1) * size[0] // columns,
                (row + 1) * size[1] // rows,
            )
            draw.rectangle(box, fill=colour)
    output = io.BytesIO()
    picture.save(output, "PNG")
    return output.getvalue()


def _stock(name):
    return ImageData(
        f"https://images/{name}.jpg",
        source=f"{name} (fake)",
        license_class="stock",
        declared_size=(1600, 1000),
        thumbnail_url=f"https://thumbs/{name}.jpg",
        description=name.replace("_", " "),
    )


class StockSource:
    """A source of four stock photos named after the query, the best first."""

    def __init__(self):
        self.asked = []

    def search(self, search):
        self.asked.append(search.query)
        return [(1.0, _stock(f"{search.query.replace(' ', '_')}-{n}")) for n in range(4)]


@pytest.fixture(autouse=True)
def pictures(monkeypatch):
    """Images at https://images/ exist, and every thumbnail at https://thumbs/ is a picture of its own; images whose
    name has "broken" in it can't be had."""
    analysis.forget()
    monkeypatch.setattr(analysis, "_download", lambda url: _png(url) if url.startswith("https://thumbs/") else None)
    jpeg = _png("stock")
    monkeypatch.setattr(
        image_util,
        "fetch_image",
        lambda url: jpeg if url.startswith("https://images/") and "broken" not in url else None,
    )
    monkeypatch.setattr(image_util, "probe", lambda url: url.startswith("https://images/") and "broken" not in url)
    yield
    analysis.forget()


@pytest.fixture(autouse=True)
def stock(monkeypatch):
    source = StockSource()
    monkeypatch.setitem(
        catalog.SOURCES,
        "fake-stock",
        catalog.Source("fake-stock", "fake", frozenset({"stock"}), source.search, lambda: True),
    )
    for name in ("photo", "gifs"):
        monkeypatch.setitem(profiles.PROFILES, name, Profile(name, "fake", (SourceUse("fake-stock"),), breadth=1))
    return source


PHOTO = ImageSlot("a photo of the slide's topic", aesthetic="photo")
GIF = ImageSlot("a gif", aesthetic="gifs")


def _schema(with_gifs=False):
    def slide(name, slot, weight):
        return SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(StaticGenerator(name), slot),
            weight_function=ConstantWeightFunction(weight),
            allowed_repeated_elements=1,
            tags=[name.lower()],
            name=name,
            llm=Recipe("image", (slot,)),
        )

    title = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
        llm=Recipe("title"),
    )
    generators = [title, slide("Photo", PHOTO, 2)] + ([slide("Gif", GIF, 2)] if with_gifs else [])
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "Talking about " + context["seed"],
        slide_generators=generators,
        max_allowed_tags={"title": 1},
    )


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    made = _schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    return made


@pytest.fixture(autouse=True)
def sheets(monkeypatch):
    """The rows of every contact sheet drawn (for the fake vision model to answer by)."""
    drawn = []
    draw = vision.contact_sheet

    def contact_sheet(rows):
        drawn.append(list(rows))
        return draw(rows)

    monkeypatch.setattr(vision, "contact_sheet", contact_sheet)
    return drawn


class FakeVision(TextProvider):
    """A vision model that answers by the rows of the last sheet drawn: with what `pick` says of them (by row number:
    a letter, or "none"), every row's first letter without one; or with `text`, or `fail`."""

    id = "fake:vision"
    capabilities = Capabilities(structured_output=True, vision=True)

    def __init__(self, sheets, pick=None, text=None, fail=None, finish="complete"):
        self.sheets = sheets
        self.pick = pick
        self.text = text
        self.fail = fail
        self.finish = finish
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        rows = self.sheets[-1]
        answer = self.pick(rows) if self.pick is not None else {str(n): "A" for n in range(1, len(rows) + 1)}
        text = self.text if self.text is not None else json.dumps(answer)
        data = parse_json(text) if request.json_schema is not None else None
        return TextResponse(
            text=text, data=data, finish=self.finish, model=self.id, input_tokens=900, output_tokens=40, cost_usd=0.0
        )


def runner_up_everywhere(rows):
    """Every row's first candidate that isn't the finder's picture."""
    return {
        str(number): next(
            letter for letter, candidate in zip(row.letters, row.candidates, strict=True) if candidate is not row.image
        )
        for number, row in enumerate(rows, 1)
    }


def finders_everywhere(rows):
    return {
        str(number): next(
            letter for letter, candidate in zip(row.letters, row.candidates, strict=True) if candidate is row.image
        )
        for number, row in enumerate(rows, 1)
    }


def _talk(vision_pick=None, llm=None, parallel=True, **options):
    _, slide_deck, _ = generator._generate_presentation(
        "fake",
        SLIDES,
        save_ppt=False,
        parallel=parallel,
        llm=llm or FakeModel(),
        vision_pick=vision_pick,
        **{**TALK, **options},
    )
    return slide_deck.to_deck(schema_name="fake")


def _pictures(deck):
    """The deck's pictures: (slide number, url, verdict)."""
    return [(number, image.url, image.vision) for number, slide in enumerate(deck.slides) for image in slide.images()]


def _urls(deck):
    return [(number, url) for number, url, _ in _pictures(deck)]


# TALKS WITH A VISION PICK


def test_without_a_vision_pick_the_finder_picks_alone():
    deck = _talk()
    assert _pictures(deck) and all(verdict is None for _, _, verdict in _pictures(deck))
    assert deck.vision_model is None and deck.usage.vision_requests == 0 and deck.usage.requests == 1
    assert _talk(vision_pick="none").to_json() == deck.to_json() == _talk(vision_pick=False).to_json()


def test_a_vision_model_picks_among_every_pictures_candidates_in_one_request(sheets):
    model = FakeVision(sheets, pick=runner_up_everywhere)
    finders = _urls(_talk())
    deck = _talk(vision_pick=model)

    assert len(model.requests) == 1 and len(sheets) == 1
    request = model.requests[0]
    assert request.purpose == "vision pick" and request.system == vision.SYSTEM
    (sheet,) = request.messages[0].images
    assert sheet.name.startswith("contact sheet ") and sheet.media_type == "image/jpeg"
    with Image.open(io.BytesIO(sheet.data)) as opened:
        assert opened.size == (sheet.width, sheet.height)
    rows = sheets[0]
    assert len(rows) == SLIDES - 1 and all(len(row.candidates) == vision.CANDIDATES for row in rows)
    assert list(request.json_schema["properties"]) == [str(number) for number in range(1, len(rows) + 1)]
    # Every picture is a runner-up of the finder's, for the same query, picked
    pictures = _pictures(deck)
    assert [number for number, _ in finders] == [number for number, _, _ in pictures]
    for (_number, finders_url), (_, url, verdict) in zip(finders, pictures, strict=True):
        assert verdict == "picked" and url != finders_url and url.rsplit("-", 1)[0] == finders_url.rsplit("-", 1)[0]
    assert len({url for _, url, _ in pictures}) == len(pictures)
    # The request is the talk's: two requests, one of them the vision pick's, by the vision model (the writer stays)
    assert deck.usage.requests == 2 and deck.usage.vision_requests == 1
    assert deck.vision_model == "fake:vision" and deck.language_model == "fake:model"
    picked = next(image for slide in deck.slides for image in slide.images())
    assert picked.look == "photo" and picked.analysis is not None and picked.query
    assert "image query of slide" in picked.query


def test_the_finders_own_picture_is_kept_and_none_is_refused(sheets):
    finders = _urls(_talk())
    kept = _talk(vision_pick=FakeVision(sheets, pick=finders_everywhere))
    refused = _talk(vision_pick=FakeVision(sheets, pick=lambda rows: {str(n): "none" for n in range(1, len(rows) + 1)}))
    assert _urls(kept) == finders and {verdict for _, _, verdict in _pictures(kept)} == {"kept"}
    assert _urls(refused) == finders and {verdict for _, _, verdict in _pictures(refused)} == {"refused"}


@pytest.mark.parametrize(
    "model",
    [
        lambda sheets: FakeVision(sheets, fail=RateLimited("the free tier ran out")),
        lambda sheets: FakeVision(sheets, fail=ProviderUnavailable("down")),
        lambda sheets: FakeVision(sheets, finish="refused"),
        lambda sheets: FakeVision(sheets, text="I can't see any pictures, sorry."),
        lambda sheets: FakeVision(sheets, text='{"1": "Z", "2": 7}'),
    ],
)
def test_failures_and_answers_it_cannot_use_keep_the_finders_pictures(sheets, model):
    finders = _talk()
    deck = _talk(vision_pick=model(sheets))
    assert _urls(deck) == _urls(finders)
    assert all(verdict is None for _, _, verdict in _pictures(deck))
    assert deck.usage.vision_requests == 1 and deck.usage.requests == 2
    # (the slides as without a vision pick)
    assert deck.slides == finders.slides


def test_an_answer_that_takes_too_long_keeps_the_finders_pictures_and_counts_as_a_failed_request(sheets, monkeypatch):
    released = threading.Event()

    class Slow(FakeVision):
        def complete(self, request):
            released.wait(10)
            return super().complete(request)

    monkeypatch.setattr(vision, "WAIT_SECONDS", 0.5)
    model = Slow(sheets, pick=runner_up_everywhere)
    try:
        deck = _talk(vision_pick=model)
    finally:
        released.set()
    assert deck.slides == _talk().slides
    assert deck.usage.requests == 2 and deck.usage.vision_requests == 1 and deck.usage.failed_requests == 1


def test_a_budget_that_allows_no_more_requests_keeps_the_finders_pictures(sheets):
    model = FakeVision(sheets, pick=runner_up_everywhere)
    deck = _talk(vision_pick=model, budget=Budget(max_requests=1))
    assert not model.requests and deck.usage.requests == 1 and deck.usage.vision_requests == 0
    assert deck.slides == _talk().slides


def test_a_paid_vision_model_never_gets_a_request_from_a_talk_at_zero_dollars(sheets):
    class Free(FakeModel):
        id = "openrouter:fake/writer:free"

    class Paid(FakeVision):
        id = "anthropic:claude-haiku-5-5"

    model = Paid(sheets, pick=runner_up_everywhere)
    deck = _talk(vision_pick=model, llm=Free(), budget=Budget(max_cost_usd=0.0))
    assert "Planned:" in deck.slides[1].notes  # (the free model wrote the talk)
    assert not model.requests and deck.slides == _talk(llm=Free()).slides
    assert deck.usage.requests == 1 and deck.usage.vision_requests == 0


def test_a_pick_that_wont_do_or_is_on_another_slide_leaves_the_finders(sheets, stock, monkeypatch):
    # Every query's second photo can't be had, and the third is the same picture everywhere
    def search(found):
        query = found.query.replace(" ", "_")
        return [
            (1.0, _stock(f"{query}-0")),
            (1.0, _stock(f"{query}-1-broken")),
            (1.0, _stock("everywhere")),
            (1.0, _stock(f"{query}-3")),
        ]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-stock", catalog.Source("fake-stock", "fake", frozenset({"stock"}), search, lambda: True)
    )

    def broken_or_everywhere(rows):
        answer = {}
        for number, row in enumerate(rows, 1):
            names = [candidate.get_image_url() for candidate in row.candidates]
            wanted = next(
                (name for name in names if "broken" in name),
                next((name for name in names if "everywhere" in name), None),
            )
            answer[str(number)] = row.letters[names.index(wanted)] if wanted else "none"
        return answer

    finders = _talk()
    deck = _talk(vision_pick=FakeVision(sheets, pick=broken_or_everywhere))
    pictures = _pictures(deck)
    assert not any("broken" in url for _, url, _ in pictures)
    assert sum(1 for _, url, _ in pictures if "everywhere" in url) <= 1  # (once at most: never on two slides)
    changed = [url for (_, url), (_, before) in zip(_urls(deck), _urls(finders), strict=True) if url != before]
    assert all("everywhere" in url for url in changed)


def test_the_same_seed_and_answers_give_the_same_deck_in_parallel_one_by_one_and_replayed(sheets, tmp_path):
    cassette = tmp_path / "answers.json"
    recording = ReplayProvider(cassette, record=FakeVision(sheets, pick=runner_up_everywhere))
    in_parallel = _talk(vision_pick=recording)
    one_by_one = _talk(vision_pick=FakeVision(sheets, pick=runner_up_everywhere), parallel=False)
    replayed = _talk(vision_pick=ReplayProvider(cassette), parallel=False)
    assert {verdict for _, _, verdict in _pictures(in_parallel)} == {"picked"}
    assert in_parallel.to_json() == one_by_one.to_json() == replayed.to_json()
    # The cassette names the sheet by its candidates, and never holds its bytes
    (entry,) = json.loads(cassette.read_text(encoding="utf-8"))["entries"].values()
    (shown,) = entry["request"]["messages"][0]["images"]
    assert set(shown) == {"media_type", "width", "height", "name"} and shown["name"].startswith("contact sheet ")
    assert cassette.stat().st_size < 20_000


def test_the_talks_seed_shuffles_the_candidates_so_the_finders_isnt_always_first(sheets):
    places = set()
    for seed in range(1, 6):
        _talk(vision_pick=FakeVision(sheets), int_seed=seed)
        places |= {row.candidates.index(row.image) for row in sheets[-1]}
    assert len(places) > 1


def test_a_streamed_talk_hands_over_the_finders_pictures_and_then_the_picked_ones(sheets):
    model = FakeVision(sheets, pick=runner_up_everywhere)
    events = list(
        generator.stream_talk("fake", SLIDES, llm=FakeModel(), vision_pick=model, theme="clean keynote", **TALK)
    )
    ready = [event for event in events if isinstance(event, SlideReady)]
    updated = [event for event in events if isinstance(event, SlideUpdated)]
    finished = events[-1]
    assert isinstance(finished, TalkFinished) and len(updated) == SLIDES - 1
    assert events.index(updated[0]) > events.index(ready[-1])  # (once the last slide is settled)
    finders = _talk(theme="clean keynote")
    for event in updated:
        before = next(earlier for earlier in ready if earlier.index == event.index)
        assert [image.url for image in before.slide.images()] == [
            image.url for image in finders.slides[event.index].images()
        ]
        assert [image.vision for image in event.slide.images()] == ["picked"]
        assert event.slide.layout == before.slide.layout
    latest = {event.index: event.slide for event in ready}
    latest.update({event.index: event.slide for event in updated})
    assert [latest[index] for index in sorted(latest)] == list(finished.deck.slides)
    assert (
        finished.deck.to_json()
        == _talk(vision_pick=FakeVision(sheets, pick=runner_up_everywhere), theme="clean keynote").to_json()
    )


def test_the_vision_model_never_gets_the_presenters_name(sheets):
    def with_name(answer):
        for key, value in answer.items():
            if key.startswith("slide_") and isinstance(value, dict) and "title" in value:
                value["title"] = f"How {PRESENTER} met an owl"

    model = FakeVision(sheets)
    _talk(vision_pick=model, llm=FakeModel(change=with_name))
    prompt = model.requests[0].messages[0].content
    assert "Ann" not in prompt and "Example" not in prompt and "How the presenter met an owl" in prompt


def test_classic_talks_have_no_vision_pick(sheets):
    model = FakeVision(sheets)
    _, slide_deck, _ = generator._generate_presentation(
        "fake", SLIDES, save_ppt=False, llm="none", vision_pick=model, **TALK
    )
    assert not model.requests and slide_deck.to_deck().usage.requests == 0


def test_looks_it_skips_and_pictures_without_runners_up_get_no_row(sheets, monkeypatch):
    made = _schema(with_gifs=True)
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    model = FakeVision(sheets, pick=runner_up_everywhere)
    deck = _talk(vision_pick=model)
    looks = {image.look: image.vision for slide in deck.slides for image in slide.images()}
    assert looks.get("gifs", "absent") is None and looks.get("photo") == "picked"
    assert all(row.image.look == "photo" for row in sheets[-1])


def test_without_its_own_vision_the_talk_asks_openrouters_free_models(sheets):
    deck = _talk(vision_pick=True)  # (FakeModel reads no pictures, and the tests have no OpenRouter key)
    assert deck.usage.vision_requests == 1 and deck.usage.failed_requests == 1
    assert deck.slides == _talk().slides


# THE CHECK


def test_the_check_reports_the_picks_and_replays_them(sheets, monkeypatch):
    made = FakeVision(sheets, pick=runner_up_everywhere)
    monkeypatch.setitem(providers._FACTORIES, "fake-writer", lambda argument: FakeModel())
    monkeypatch.setitem(providers._FACTORIES, "fake-vision", lambda argument: made)
    report = benchmark.check_talk("owls", 3, "fake", SLIDES, True, "fake-writer", vision_pick="fake-vision")
    assert report.deterministic is True and not report.errors
    assert report.metrics["vision_pick"] == {"picked": SLIDES - 1, "kept": 0, "refused": 0}
    assert report.metrics["vision_model"] == "fake:vision" and report.metrics["usage"]["vision_requests"] == 1
    assert len(made.requests) == 1  # (the second run replayed its answer)
    summary = benchmark._report([report], "fake", SLIDES, [3], "fake-writer")["summary"]
    assert summary["vision_pick"] == {"picked": 5, "kept": 0, "refused": 0, "requests": 1, "models": ["fake:vision"]}


def test_deck_metrics_count_the_verdicts():
    metrics = deck_metrics(_talk())
    assert metrics["vision_pick"] == {"picked": 0, "kept": 0, "refused": 0} and metrics["vision_model"] is None


# THE PARTS


def _row(name, candidates=4, slide_nr=1, wants=""):
    images = [_stock(f"{name}-{n}") for n in range(candidates)]
    thumbnails = [Image.open(io.BytesIO(_png(name + str(n)))).convert("RGB") for n in range(candidates)]
    return vision._Row(slide_nr, None, images[0], images, thumbnails, f"what slide {slide_nr} says", wants)


@pytest.mark.parametrize("count", [1, 6, 7, 10])
def test_the_sheet_has_a_row_for_every_picture_one_under_another_with_what_it_asks_for(count):
    long = (
        "an owl in a tiny lab coat explaining quantum physics to three very confused pigeons on a windowsill, while a "
        "cat takes notes and a squirrel sells popcorn to everyone in the front row"
    )
    rows = [_row(f"picture{number}", slide_nr=number, wants=long) for number in range(count)]
    sheet = vision.contact_sheet(rows)
    row_width = vision.LABEL_WIDTH + vision.CANDIDATES * vision.CELL[0] + (vision.CANDIDATES - 1) * vision.GAP
    assert row_width < sheet.width < row_width + 30
    assert count * vision.CELL[1] < sheet.height < count * (vision.CELL[1] + vision.GAP) + 20
    with Image.open(io.BytesIO(sheet.data)) as opened:
        assert opened.format == "JPEG" and opened.size == (sheet.width, sheet.height)
    # What a row asks for fits beside it, cut short when it's long
    lines = vision._wrapped(long, vision._font(18, vision._TEXT_FONT), vision.LABEL_WIDTH - 2 * vision.GAP, 5)
    assert len(lines) == 5 and lines[-1].endswith("…") and lines[0].startswith("an owl")
    # Named by its candidates, in their order: the same candidates, the same name, whatever the thumbnails
    again = vision.contact_sheet(
        [vision._Row(row.slide_nr, None, row.image, row.candidates, row.thumbnails[::-1], "") for row in rows]
    )
    assert again.name == sheet.name
    other = vision.contact_sheet(
        [vision._Row(row.slide_nr, None, row.image, row.candidates[::-1], row.thumbnails, "") for row in rows]
    )
    assert other.name != sheet.name or count == 0


def test_the_request_asks_what_each_row_shows_and_a_letter_or_none_and_names_what_each_shows():
    rows = [_row("owl"), _row("barn", candidates=2, slide_nr=4)]
    rows[0].image.query = "an owl reading a newspaper"
    request = vision.picking_request(rows, vision.contact_sheet(rows))
    prompt = request.messages[0].content
    assert (
        "1. Slide 2's picture shows an owl reading a newspaper." in prompt
        and 'The slide says: "what slide 1 says"' in prompt
    )
    assert "2. Slide 5's picture shows" in prompt
    first, second = (request.json_schema["properties"][number] for number in ("1", "2"))
    assert list(first["properties"]) == ["shows", "pick"] and first["required"] == ["shows", "pick"]
    assert first["properties"]["pick"]["enum"] == ["A", "B", "C", "D", "none"]
    assert second["properties"]["pick"]["enum"] == ["A", "B", "none"]
    assert request.json_schema["required"] == ["1", "2"] and request.json_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            '{"1": {"shows": "A: an owl, B: a barn", "pick": "B"}, "2": {"shows": "a cow", "pick": "none"}}',
            {1: 1, 2: None},
        ),
        ('{"1": {"shows": "owls", "pick": "1D"}, "2": {"shows": "barns"}}', {1: 3}),
        ('{"1": {"shows": "owls", "pick": "A"}, "2": {"shows": "barns", "pi', {1: 0}),  # (cut off)
        ('{"1": "B", "2": "none"}', {1: 1, 2: None}),
        ('```json\n{"1": "1C", "2": "b"}\n```', {1: 2, 2: 1}),
        ('{"1": null, "2": "E"}', {1: None}),
        ('{"1": "A"}', {1: 0}),
        ("1: B\n2: none", {1: 1, 2: None}),
        ("Row 1 = 1D, row 2: A", {1: 3, 2: 0}),
        ("No idea.", {}),
    ],
)
def test_answers_are_read_by_row_with_a_letter_of_the_rows_or_none(text, expected):
    rows = [_row("owl"), _row("barn", candidates=2)]
    response = TextResponse(text=text, data=parse_json(text))
    assert vision.read_answer(response, rows) == expected


def test_the_presenters_name_and_its_parts_are_left_out():
    assert (
        vision._without_name("Meet Ann Example, and Ann's owl", PRESENTER)
        == "Meet the presenter, and the presenter's owl"
    )
    assert vision._without_name("Prof. Anna Tomy on anatomy", "Prof. Anna Tomy") == "the presenter on anatomy"
    assert vision._without_name("Nothing to hide", None) == "Nothing to hide"


def test_the_finder_keeps_runners_up_only_for_planned_slides_of_a_talk_with_a_vision_pick(stock):
    def find(with_vision, planned):
        talk = context.ImageContext(
            vision=vision.VisionPick(FakeVision([]), random_util.Rng(1)) if with_vision else None
        )
        with context.for_talk(talk), random_util.use(random_util.Rng(7)):
            if planned:
                with generator_util.as_planned():
                    return PHOTO.find("owls")
            return PHOTO.find("owls")

    plain, kept = find(False, True), find(True, True)
    assert plain == kept and plain.runners_up is None  # (the same picture: a vision pick draws nothing)
    assert kept.runners_up is not None and kept.runners_up.look == "photo"
    assert kept not in kept.runners_up.images and len(kept.runners_up.images) == 3
    assert kept.runners_up.intent == PHOTO.intent
    assert find(True, False).runners_up is None  # (a classic search keeps none)


def test_which_model_a_vision_pick_asks(monkeypatch):
    talk_model = FakeModel()
    claude = ClaudeProvider("claude-haiku-5-5")
    for off in (None, False, "none", "off", ""):
        assert vision.provider_for(off, talk_model) is None
    assert vision.provider_for(True, claude) is claude and vision.provider_for("on", claude) is claude
    free = vision.provider_for(True, talk_model)
    assert (
        isinstance(free, OpenRouterProvider) and free.models == vision.FREE_MODELS and free.effort == vision.FREE_EFFORT
    )
    assert isinstance(vision.provider_for("openrouter", claude), OpenRouterProvider)
    assert vision.provider_for("openrouter", claude).models == vision.FREE_MODELS
    named = vision.provider_for("openrouter:google/gemma-4-31b-it:free", claude)
    assert isinstance(named, OpenRouterProvider) and named.models == ("google/gemma-4-31b-it:free",)
    assert isinstance(vision.provider_for("anthropic:claude-haiku-5-5", None), ClaudeProvider)
    replayed = ReplayProvider("nowhere.json")
    assert vision.provider_for(True, replayed) is replayed
    with pytest.raises(ValueError):
        vision.check_spec("nonsense:model")
    assert generator.get_argument_parser().parse_args(["--vision_pick"]).vision_pick == "on"
    assert generator.get_argument_parser().parse_args([]).vision_pick is None
    assert generator.get_argument_parser().parse_args(["--vision_pick", "openrouter"]).vision_pick == "openrouter"


# PICTURES IN REQUESTS


def _picture_request():
    sheet = ImagePart(data=b"\xff\xd8 not really a jpeg", width=1748, height=936, name="contact sheet 0123")
    return TextRequest.ask("vision pick", "Which one?", images=(sheet,), system="You pick pictures.")


def test_providers_send_pictures_as_their_apis_take_them():
    request = _picture_request()
    data_url = "data:image/jpeg;base64," + request.messages[0].images[0].base64()
    openrouter = OpenRouterProvider(["nvidia/nemotron-3.5-super-vl:free"], effort="minimal").arguments(request)
    assert openrouter["messages"][1]["content"] == [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": "Which one?"},
    ]
    assert openrouter["extra_body"]["reasoning"] == {"effort": "minimal"}
    claude = ClaudeProvider("claude-haiku-5-5").arguments(request)
    assert claude["messages"][0]["content"][0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": request.messages[0].images[0].base64()},
    }
    assert claude["messages"][0]["content"][1] == {"type": "text", "text": "Which one?"}
    openai = OpenAIProvider("gpt-5-mini").arguments(request)
    assert openai["input"][0]["content"] == [
        {"type": "input_image", "image_url": data_url, "detail": "high"},
        {"type": "input_text", "text": "Which one?"},
    ]
    # Messages without pictures go as before
    plain = TextRequest.ask("talk plan", "Write a talk")
    assert OpenRouterProvider().arguments(plain)["messages"][0]["content"] == "Write a talk"
    assert ClaudeProvider().arguments(plain)["messages"][0]["content"] == "Write a talk"


def test_a_pictures_tokens_count_toward_the_worst_case_and_its_bytes_toward_nothing_recorded():
    request = _picture_request()
    sheet = request.messages[0].images[0]
    assert 1300 < sheet.tokens < 1600  # (scaled down to about 1.15 megapixels, at 750 pixels a token)
    without = TextRequest.ask("vision pick", "Which one?", system="You pick pictures.")
    model = "anthropic:claude-haiku-5-5"
    extra = prices.worst_case_cost(model, request) - prices.worst_case_cost(model, without)
    assert extra == pytest.approx(sheet.tokens * 0.10 / 1e6)
    dumped = request.model_dump(mode="json")
    assert "data" not in dumped["messages"][0]["images"][0] and "not really" not in repr(request)
    assert request.shows_images and not without.shows_images


def test_a_cassette_answers_the_same_sheet_whatever_its_bytes(tmp_path):
    cassette = tmp_path / "answers.json"
    recorded = TextResponse(text='{"1": "B"}', model="fake:vision")

    class Once(TextProvider):
        id = "fake:vision"

        def complete(self, request):
            return recorded

    first = ImagePart(data=b"one", width=10, height=10, name="contact sheet abc")
    ReplayProvider(cassette, record=Once()).complete(TextRequest.ask("vision pick", "Which?", images=(first,)))
    second = first.model_copy(update={"data": b"two"})
    assert ReplayProvider(cassette).complete(TextRequest.ask("vision pick", "Which?", images=(second,))) == recorded


def test_a_request_without_pictures_keeps_the_cassette_key_it_had_before_requests_could_show_any():
    request = TextRequest.ask("talk plan", "Write a talk", system="Be funny", max_output_tokens=900)
    before = request.model_dump(mode="json")
    for message in before["messages"]:
        del message["images"]
    canonical = json.dumps(before, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert request_key(request) == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_two_recorders_on_one_cassette_keep_both_answers(tmp_path):
    cassette = tmp_path / "answers.json"

    class Says(TextProvider):
        def __init__(self, text):
            self.id = "fake:" + text
            self.text = text

        def complete(self, request):
            return TextResponse(text=self.text, model=self.id)

    talk, picking = ReplayProvider(cassette, record=Says("talk")), ReplayProvider(cassette, record=Says("picks"))
    talk.complete(TextRequest.ask("talk plan", "Write"))
    picking.complete(TextRequest.ask("vision pick", "Pick"))
    replay = ReplayProvider(cassette)
    assert replay.complete(TextRequest.ask("talk plan", "Write")).text == "talk"
    assert replay.complete(TextRequest.ask("vision pick", "Pick")).text == "picks"
    assert os.path.isfile(cassette)
