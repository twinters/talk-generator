"""Offline tests of the pictures that diagrams have now and then (docs/v5-plan.md, D64): a weird but related picture in
some of a diagram's boxes (a process's steps, a pyramid's levels, an iceberg's tip, a matrix's quadrants, beside a Venn
diagram's circles), which appears with its box's text; and a picture by a trend's named point, on a click of its own,
where every renderer has the point."""

import itertools

import pytest
from PIL import Image

from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, themes
from talkgenerator.images import finder
from talkgenerator.models.deck import Box, ChartElement, Deck, ImageElement, ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import kinds, languages, prompt
from talkgenerator.plan.kinds import KINDS, BoxPictures, Recipe
from talkgenerator.plan.realize import realize
from talkgenerator.render import charts, preview, reveal
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema.formats import KindSlideGenerator
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import diagram, slide_texts
from talkgenerator.util import random_util

ENGLISH = languages.LANGUAGES["en"]
PICTURED = ("venn", "matrix", "pyramid", "funnel", "cycle", "iceberg", "process", "flowchart")
TEXTS = {
    "venn": {"title": "Love", "circle_1": "Cats", "circle_2": "Dogs", "overlap": "Naps"},
    "matrix": {
        "title": "Pets",
        "x_left": "Lazy",
        "x_right": "Busy",
        "y_bottom": "Cold",
        "y_top": "Cuddly",
        "top_left": "Nappers",
        "top_right": "Fans",
        "bottom_left": "Rocks",
        "bottom_right": "Bees",
        "dot": "My ex",
        "dot_quadrant": "bottom left",
    },
    "pyramid": {"title": "Needs", "level_1": "Cake", "level_2": "Naps", "level_3": "Wi-Fi"},
    "funnel": {"title": "Funnel", "stage_1": "Everyone", "stage_2": "Some", "stage_3": "Me"},
    "cycle": {"title": "Cycle", "step_1": "Wake", "step_2": "Coffee", "step_3": "Panic", "step_4": "Nap"},
    "iceberg": {"title": "Iceberg", "tip": "Cats", "hidden_1": "Plots", "hidden_2": "Lasers"},
    "process": {"title": "Method", "step_1": "Ask", "step_2": "Guess", "step_3": "Publish"},
    "flowchart": {"question": "Hungry?", "yes_step": "Eat cake", "no_step": "Eat cake anyway", "end": "Nap"},
}


@pytest.fixture
def picture(tmp_path):
    """A picture on this computer: a new one each time it's called."""
    count = itertools.count()

    def make():
        path = tmp_path / f"picture-{next(count)}.png"
        Image.new("RGB", (400, 300), "#d98c3a").save(path)
        return ImageData(str(path), source="Test", source_url=f"https://example.com/{path.stem}")

    return make


def _built(kind, images, seed=1, **texts):
    """A slide of the kind, with the pictures it keeps credited (as a planned slide's are: see realize)."""
    with random_util.use(random_util.Rng(seed)):
        slide = KINDS[kind].build({**TEXTS[kind], **texts}, images, ENGLISH)
    for image in slide.image_store().values():
        slide.add_source(image.get_source(), image.get_source_url(), image.get_credit(), image=image)
    return slide


def _every_box(kind, picture):
    return {BoxPictures.slot(box): picture() for box in KINDS[kind].pictures.boxes}


# HOW OFTEN, AND WHICH BOXES


@pytest.mark.parametrize("kind", PICTURED)
def test_a_diagram_has_pictures_in_some_of_its_boxes_now_and_then(kind):
    pictures = KINDS[kind].pictures
    recipe = Recipe(kind)
    varied = [recipe.varied(random_util.Rng(seed)) for seed in range(400)]
    pictured = [version for version in varied if version.pictures]
    # (a matrix's pictures go in its named quadrants: the variant with names in them)
    share = len(pictured) / len(varied)
    expected = pictures.odds * (0.4 if kind == "matrix" else 1)
    assert expected - 0.08 <= share <= expected + 0.08
    assert all(
        len(version.pictures) <= pictures.most and set(version.pictures) <= set(pictures.boxes) for version in varied
    )
    assert any(len(version.pictures) == 2 for version in pictured) == (pictures.most == 2)
    for version in pictured[:5]:
        slots = [BoxPictures.slot(box) for box in version.pictures]
        assert version.image_queries() == slots and version.optional_slots() == slots
        assert [name for name, _ in version.slots()] == slots
        assert "weird but related picture" in version.brief
        assert all(f"{slot}_query" in prompt.slide_schema(version)["properties"] for slot in slots)
    # A slide without pictures asks for none
    plain = next(version for version in varied if not version.pictures)
    assert plain.image_queries() == [] and plain.slots() == []


def test_the_picture_roll_leaves_a_recipes_own_variant_as_it_was():
    recipe = next(
        generator.llm for generator in get_schema("default").slide_generators if generator.name == "Trend Chart"
    )
    for seed in range(30):
        varied = recipe.varied(random_util.Rng(seed))
        with random_util.use(random_util.Rng(seed)):
            expected = random_util.weighted_random([(variant.weight, variant) for variant in recipe.variants])
        assert varied.omit == recipe.omit | expected.omit


# HOW A PLANNED SLIDE GETS THEM


def test_a_picture_that_isnt_found_leaves_its_box_empty(monkeypatch, picture):
    recipe = Recipe("pyramid", pictures=("level_1", "level_2"))
    found = picture()
    monkeypatch.setattr(finder, "find", lambda slot, query=None, avoid=(): found if query == "cake" else None)
    plan = SlidePlan(
        kind="pyramid",
        concept="needs",
        texts=TEXTS["pyramid"],
        images={"level_1_picture": "cake", "level_2_picture": "nothing at all"},
    )
    problems: list[str] = []
    result = realize(plan, recipe, {"seed": "needs"}, random_util.Rng(1), 0, problems=problems)
    assert result is not None, problems
    slide, _ = result
    roles = {element.role for element in slide.to_deck_slide().elements}
    assert "level_1_picture" in roles and "level_2_picture" not in roles
    assert len(slide.to_deck_slide().credits) == 1  # (the one it has)


# WHERE THEY GO, AND WHEN THEY APPEAR


@pytest.mark.parametrize("kind", PICTURED)
def test_a_boxs_picture_appears_with_its_text(kind, picture):
    slide = _built(kind, _every_box(kind, picture)).to_deck_slide()
    clicks = {element.role: getattr(element, "appears_on_click", None) for element in slide.elements}
    for box in KINDS[kind].pictures.boxes:
        role = BoxPictures.slot(box)
        if kind == "matrix" and box == "bottom_left":
            assert role not in clicks  # (its quadrant has the dot: no room)
            continue
        assert role in clicks
        assert clicks[role] == clicks.get(box)  # (a Venn diagram's and a matrix's are there from the start)
    assert all(
        isinstance(element, ImageElement) and element.fit == "cover"
        for element in slide.elements
        if element.role.endswith("_picture")
    )


def _texts_and_pictures(slide):
    texts = [element for element in slide.elements if isinstance(element, TextElement) and element.role != "decoration"]
    pictures = [element for element in slide.elements if isinstance(element, ImageElement)]
    return texts, pictures


def _apart(box, other):
    return (
        box.x + box.w <= other.x or other.x + other.w <= box.x or box.y + box.h <= other.y or other.y + other.h <= box.y
    )


@pytest.mark.parametrize("family", ["dark minimal", "kids", "hacker terminal", "newspaper"])
@pytest.mark.parametrize("kind", PICTURED)
def test_pictures_in_boxes_keep_clear_of_the_texts_and_read_in_every_family(kind, family, picture):
    built = _built(kind, _every_box(kind, picture))
    deck = engine.lay_out(
        Deck(generator="test", seed=4, slides=(built.to_deck_slide(),)), themes.pick(family, random_util.Rng(2))
    )
    (slide,) = deck.slides
    texts, pictures = _texts_and_pictures(slide)
    assert pictures, slide.layout
    for element in pictures:
        assert element.box is not None and element.box.w >= 96 and element.box.h >= 72
        assert 0 <= element.box.x and element.box.x + element.box.w <= 1920 and element.box.y + element.box.h <= 1080
        assert all(_apart(element.box, text.box) for text in texts), (element.role, slide.layout)
    assert all(_apart(one.box, other.box) for one, other in itertools.combinations(pictures, 2))
    assert [finding for finding in check_design(deck) if finding.severity == "error"] == []
    # (every picture it shows is credited, and only those)
    assert len(slide.credits) == len(pictures)


def test_a_process_across_has_its_steps_picture_above_its_text(picture):
    built = _built("process", {"step_2_picture": picture()})
    theme = themes.pick("dark minimal", random_util.Rng(2))
    placed = engine.lay_out_slide(built.to_deck_slide(), theme, random_util.Rng(0), previous="v5/process")
    assert placed.layout == "v5/process-across"
    text = placed.element("step_2")
    shown = placed.element("step_2_picture")
    assert (
        shown.box.y + shown.box.h <= text.box.y
        and abs((shown.box.x + shown.box.w / 2) - (text.box.x + text.box.w / 2)) < 1
    )


def test_a_cycle_with_a_picture_keeps_its_ring_under_the_title(picture):
    built = _built("cycle", {"step_2_picture": picture()}).to_deck_slide()
    assert engine.layouts_for(built) == ["v5/cycle"]  # (beside a title, the ring has no room in its middle)
    assert "v5/cycle-side" in engine.layouts_for(_built("cycle", {}).to_deck_slide())


def test_a_picture_without_room_stays_out_with_its_credit(picture):
    # A Venn diagram's labels beside its circles take the room its pictures have beside the circles
    long = {"circle_1": "Brandweerkazernedeurcompartiment", "circle_2": "Ziekenhuisparkeerplaatsautomaat"}
    built = _built("venn", _every_box("venn", picture), **long).to_deck_slide()
    assert len(built.credits) == 2
    (slide,) = engine.lay_out(
        Deck(generator="test", slides=(built,)), themes.pick("dark minimal", random_util.Rng(2))
    ).slides
    assert not [element for element in slide.elements if isinstance(element, ImageElement)]
    assert slide.credits == ()


def test_a_matrix_has_pictures_only_in_quadrants_without_a_dot(picture):
    shown = _built("matrix", _every_box("matrix", picture), dot_quadrant="top right").to_deck_slide()
    assert sorted(element.role for element in shown.elements if isinstance(element, ImageElement)) == [
        "bottom_left_picture",
        "bottom_right_picture",
        "top_left_picture",
    ]
    things = {"top_left": "", "top_right": "", "bottom_left": "", "bottom_right": "", "top_left_things": "Cats"}
    dotted = _built("matrix", _every_box("matrix", picture), **things).to_deck_slide()
    pictured = {element.role for element in dotted.elements if isinstance(element, ImageElement)}
    assert "top_left_picture" not in pictured and "bottom_left_picture" not in pictured


@pytest.mark.parametrize("kind", ["venn", "matrix", "pyramid", "iceberg"])
def test_a_classic_deck_draws_the_pictures_of_its_boxes_too(kind, picture):
    built = _built(kind, _every_box(kind, picture))
    presentation = render_pptx(Deck(generator="test", slides=(built.to_deck_slide(),)))
    pictures = [shape for shape in presentation.slides[0].shapes if shape.shape_type == 13]  # (pictures)
    expected = len([element for element in built.to_deck_slide().elements if isinstance(element, ImageElement)])
    assert len(pictures) == expected >= 1
    for shape in pictures:
        assert 0 <= shape.left and shape.left + shape.width <= presentation.slide_width


def test_the_preview_draws_a_diagrams_pictures(picture):
    built = _built("pyramid", _every_box("pyramid", picture))
    deck = engine.lay_out(
        Deck(generator="test", slides=(built.to_deck_slide(),)), themes.pick("kids", random_util.Rng(2))
    )
    image = preview.slide_image(deck.slides[0], deck.style, images=built.image_store())
    assert image.size[0] > 0


# CLASSIC DIAGRAMS


def _classic(generator, odds_seeds=200):
    shown = []
    for seed in range(odds_seeds):
        with random_util.use(random_util.Rng(seed)):
            shown.append(generator({"seed": "cats", "topic": "cats"}))
    return shown


def test_classic_diagrams_have_pictures_now_and_then(picture):
    def generate(context):
        return ("The cat pyramid", "Cats", "Naps", "Wi-Fi")

    asked = []

    def source(context):
        asked.append(context["seed"])
        return picture()

    pictured = slide_texts.pictured(generate, source, slide_texts.numbered_boxes("level"))
    made = _classic(pictured)
    with_pictures = [generated for generated in made if isinstance(generated[-1], slides.Pictures)]
    assert 0.25 <= len(with_pictures) / len(made) <= 0.45
    assert all(set(generated[-1].by_box()) <= {"level_1", "level_2", "level_3"} for generated in with_pictures)
    assert set(asked) <= {"Cats", "Naps", "Wi-Fi"}  # (a picture of its box's text)
    # The slide gets them by name, and they're among what it's made of
    generator = slide_generator_types.DrawnSlideGenerator(lambda context: with_pictures[0], slides.PyramidSlide)
    slide, generated = generator.generate_slide({"seed": "cats"}, (set(), 0))
    assert all(image in generated for image in with_pictures[0][-1].by_box().values())
    roles = {element.role for element in slide.to_deck_slide().elements}
    assert {f"{box}_picture" for box in with_pictures[0][-1].by_box()} <= roles


def test_a_formats_classic_diagram_has_pictures_now_and_then(monkeypatch, picture):
    monkeypatch.setattr(finder, "find", lambda slot, query=None, avoid=(): picture())
    generator = KindSlideGenerator("process", lambda context: (TEXTS["process"], {}))
    made = []
    for seed in range(120):
        with random_util.use(random_util.Rng(seed)):
            made.append(generator.generate_slide({"seed": "cats"}, (set(), 0)))
    pictured = [slide for slide, _ in made if any(role.endswith("_picture") for role in slide._arguments)]
    assert 0.2 <= len(pictured) / len(made) <= 0.5


def test_classic_matrices_and_venn_diagrams_name_their_boxes_for_pictures():
    venn = diagram.VennDiagram(circles=("Cats", "Dogs", "Owls"), overlap="Naps")
    assert diagram.venn_boxes(("Love", venn)) == {"circle_1": "Cats", "circle_2": "Dogs"}
    matrix = diagram.matrix("A", "B", "C", "D", ("Nappers", "Fans", "Rocks", ""), "Me", "top right")
    assert diagram.matrix_boxes(("Pets", matrix)) == {"top_left": "Nappers", "bottom_left": "Rocks"}


# A PICTURE BY A TREND'S NAMED POINT


def _trend(images, seed=7, **texts):
    with random_util.use(random_util.Rng(seed)):
        return KINDS["chart_trend"].build(
            {
                "title": "Tiredness",
                "x_axis": "Hours",
                "y_axis": "Yawns",
                "shape": "hockey stick",
                "event": "I got a cat",
                **texts,
            },
            images,
            ENGLISH,
        )


def test_a_trend_has_a_picture_by_its_named_point_now_and_then():
    recipe = Recipe("chart_trend")
    varied = [recipe.varied(random_util.Rng(seed)) for seed in range(400)]
    share = sum(1 for version in varied if version.pictures == ("event",)) / len(varied)
    assert kinds.TREND_PICTURE_ODDS - 0.08 <= share <= kinds.TREND_PICTURE_ODDS + 0.08
    pictured = next(version for version in varied if version.pictures)
    assert pictured.image_queries() == ["event_picture"] and "by the moment's point" in pictured.brief


@pytest.mark.parametrize("second_line", ["", "My cat"])
def test_the_picture_comes_on_a_click_of_its_own(second_line, picture):
    slide = _trend({"event_picture": picture()}, second_line=second_line).to_deck_slide()
    shown = slide.element("point_picture")
    assert isinstance(shown, ImageElement) and shown.appears_on_click == (2 if second_line else 1)
    assert reveal.clicks(slide) == shown.appears_on_click
    theme = themes.pick("clean keynote", random_util.Rng(2))
    (placed,) = engine.lay_out(Deck(generator="test", slides=(slide,)), theme).slides
    assert placed.element("point_picture").appears_on_click == shown.appears_on_click  # (after the second line's)
    # Without a named point, there's no picture
    assert _trend({"event_picture": picture()}, event="").to_deck_slide().element("point_picture") is None


@pytest.mark.parametrize("layout", ["v5/chart", "v5/chart-side"])
@pytest.mark.parametrize("shape", ["hockey stick", "peak", "dip", "rising", "crash"])
def test_the_picture_goes_by_the_point_clear_of_its_name_and_the_lines(shape, layout, picture):
    slide = _trend({"event_picture": picture()}, shape=shape, second_line="My cat").to_deck_slide()
    theme = themes.pick("dark minimal", random_util.Rng(2))
    placed = engine.lay_out_slide(
        slide, theme, random_util.Rng(0), previous="v5/chart" if layout != "v5/chart" else "x"
    )
    if placed.layout != layout:
        pytest.skip("the title doesn't fit beside the chart")
    chart = placed.element("chart")
    assert isinstance(chart, ChartElement)
    plot = charts.trend_plot(chart.chart, chart.box.w, chart.box.h)
    shown = placed.element("point_picture").box
    inside = Box(
        x=chart.box.x + plot.left,
        y=chart.box.y + plot.top - charts.NAMED_DOT,
        w=plot.right - plot.left,
        h=plot.bottom - plot.top + charts.NAMED_DOT,
    )
    assert inside.x - 1 <= shown.x and shown.x + shown.w <= inside.x + inside.w + 1
    assert inside.y - 1 <= shown.y and shown.y + shown.h <= inside.y + inside.h + 1
    series, index = charts.named_point(chart.chart)
    x, y = charts.trend_points(chart.chart, plot)[series][index]
    x, y = chart.box.x + x, chart.box.y + y
    assert not (shown.x - 18 <= x <= shown.x + shown.w + 18 and shown.y - 18 <= y <= shown.y + shown.h + 18)
    lines = [element for element in placed.elements if isinstance(element, ShapeElement) and element.role == "pin"]
    assert all(line.part_of == "point_picture" for line in lines)


def test_a_pinned_trend_has_its_plot_where_every_renderer_has_it(picture):
    slide = _trend({"event_picture": picture()}).to_deck_slide()
    deck = engine.lay_out(Deck(generator="test", slides=(slide,)), themes.pick("clean keynote", random_util.Rng(2)))
    presentation = render_pptx(deck)
    (frame,) = [shape for shape in presentation.slides[0].shapes if shape.has_chart]
    chart = frame.chart
    manual = chart._chartSpace.xpath(".//c:plotArea/c:layout/c:manualLayout")
    assert manual and manual[0].xpath("./c:layoutTarget/@val") == ["inner"]
    spec = deck.slides[0].element("chart")
    plot = charts.trend_plot(spec.chart, spec.box.w, spec.box.h)
    x = float(manual[0].xpath("./c:x/@val")[0])
    assert abs(x - plot.left / spec.box.w) < 1e-4
    largest = max(value for series in spec.chart.series for value in series.values)
    assert chart.value_axis.maximum_scale == charts.axis_top(largest) and chart.value_axis.minimum_scale == 0
    assert chart._chartSpace.xpath(".//c:valAx/c:crossBetween/@val") == ["between"]
    # A trend without a picture keeps PowerPoint's own layout
    plain = engine.lay_out(
        Deck(generator="test", slides=(_trend({}).to_deck_slide(),)), themes.pick("clean keynote", random_util.Rng(2))
    )
    (frame,) = [shape for shape in render_pptx(plain).slides[0].shapes if shape.has_chart]
    assert not frame.chart._chartSpace.xpath(".//c:plotArea/c:layout/c:manualLayout")


def test_a_classic_trend_shows_its_picture_on_a_click_after_its_second_line(picture):
    slide = _trend({"event_picture": picture()}, second_line="My cat").to_deck_slide()
    presentation = render_pptx(Deck(generator="test", slides=(slide,)))
    ppt_slide = presentation.slides[0]
    assert len([shape for shape in ppt_slide.shapes if shape.shape_type == 13]) == 1
    clicks = ppt_slide.element.xpath(".//p:timing//p:cond[@delay='indefinite']")
    assert len(clicks) == 2  # (the second line, then the picture)


def test_axis_top_is_a_round_number_above_the_largest_value():
    assert charts.axis_top(0) == 1
    assert charts.axis_top(97) == 120  # (100 is too close: PowerPoint goes a step higher)
    assert charts.axis_top(42) == 50
    assert charts.axis_top(3.2) == 4


def test_a_trends_plot_leaves_room_as_the_site_does():
    spec = _trend({}).to_deck_slide().element("chart").chart
    plot = charts.trend_plot(spec, 1000, 600)
    # (talk-generator-web's chart.component.ts: 8 px margins, 64 for each axis title, 64.8 for a legend, 64 on top)
    assert (plot.left, plot.top, plot.right) == (8 + 64, 8 + 64, 1000 - 8)
    assert plot.bottom == 600 - 8 - 64 - (64.8 if any(series.name for series in spec.series) else 0)
    points = charts.trend_points(spec, plot)
    span = (plot.right - plot.left) / len(spec.series[0].values)
    assert points[0][0][0] == pytest.approx(plot.left + span / 2)


def test_a_classic_trend_has_a_picture_by_its_moment_now_and_then(monkeypatch, picture):
    from talkgenerator.sources import chart

    monkeypatch.setattr(chart, "correlation_title_generator", lambda context: "Naps over time")
    monkeypatch.setattr(chart, "trend_event_generator", lambda context: "I got a cat")
    asked = []

    def source(context):
        asked.append(context["seed"])
        return picture()

    generate = slide_texts.pictured(chart.generate_trend_chart, source, chart.trend_boxes, 1, kinds.TREND_PICTURE_ODDS)
    made = _classic(generate, 200)
    with_event = [generated for generated in made if any(name for _, _, name in generated[7])]
    pictured = [generated for generated in with_event if isinstance(generated[-1], slides.Pictures)]
    assert 0.35 <= len(pictured) / len(with_event) <= 0.65 and set(asked) == {"I got a cat"}
    assert not any(isinstance(generated[-1], slides.Pictures) for generated in made if generated not in with_event)
    generator = slide_generator_types.ChartSlideGenerator(lambda context: pictured[0])
    slide, generated = generator.generate_slide({"seed": "cats"}, (set(), 0))
    shown = slide.to_deck_slide().element("point_picture")
    assert isinstance(shown, ImageElement) and shown.appears_on_click == 1
