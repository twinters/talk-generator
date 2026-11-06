"""Offline tests of the diagrams that came with v5, drawn as shapes: Venn diagrams (two or three see-through circles
and the punchline where they overlap) and 2×2 matrices (two axes, four quadrants and one named dot, the punchline).
"""

import json
import math

import pytest
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pydantic import ValidationError

from talkgenerator.checks.deck import check_completeness, check_language, check_leftovers
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.models import classic
from talkgenerator.models.deck import Deck, DeckSlide, DiagramElement, MatrixDiagram, TextElement, VennDiagram
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import clean_text, realize
from talkgenerator.render import diagrams
from talkgenerator.render.powerpoint import render_pptx, render_slide
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types, slides
from talkgenerator.sources import conceptnet, diagram
from talkgenerator.util import random_util

ENGLISH = languages.LANGUAGES["en"]
VENN = {
    "title": "My love life",
    "circle_1": "Things I love",
    "circle_2": "Things that love me back",
    "overlap": "Cheese",
}
MATRIX = {
    "title": "The pet owner's matrix",
    "x_left": "Low effort",
    "x_right": "High effort",
    "y_bottom": "Barely loves you",
    "y_top": "Loves you a lot",
    "top_left": "Dogs",
    "top_right": "Children",
    "bottom_left": "Rocks",
    "bottom_right": "Cats",
    "dot": "My grandmother's parrot",
    "dot_quadrant": "bottom right",
}


def _venn(**texts):
    return KINDS["venn"].build({**VENN, **texts}, {}, ENGLISH)


def _matrix(seed=1, **texts):
    with random_util.use(random_util.Rng(seed)):
        return KINDS["matrix"].build({**MATRIX, **texts}, {}, ENGLISH)


def _diagram(slide):
    element = slide.to_deck_slide().element("diagram")
    assert isinstance(element, DiagramElement)
    return element.diagram


def _drawn(slide):
    """The slide in a new PowerPoint, its shapes by name, and the presentation."""
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    ppt_slide = slide.create_powerpoint_slide(presentation)
    return ppt_slide, {shape.name: shape for shape in ppt_slide.shapes}, presentation


def _centre(shape):
    return shape.left + shape.width / 2, shape.top + shape.height / 2


def _inside(point, circle):
    (x, y), (cx, cy) = point, _centre(circle)
    return math.hypot(x - cx, y - cy) < circle.width / 2


def _within(shape, left, top, right, bottom):
    return (
        left <= shape.left
        and top <= shape.top
        and shape.left + shape.width <= right
        and shape.top + shape.height <= bottom
    )


def _on_the_slide(ppt_slide, presentation):
    return all(_within(shape, 0, 0, presentation.slide_width, presentation.slide_height) for shape in ppt_slide.shapes)


def _alpha(shape):
    colour = shape._element.spPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    alpha = colour.find(qn("a:alpha"))
    return int(alpha.get("val")) if alpha is not None else None


def _text(shape):
    return shape.text_frame.text


# VENN DIAGRAMS


def test_a_venn_diagram_has_two_circles_and_its_overlap_as_the_punchline():
    deck_slide = _venn().to_deck_slide()
    assert (deck_slide.type, deck_slide.layout) == ("diagram", "classic/diagram")
    assert [(element.kind, element.role) for element in deck_slide.elements] == [
        ("text", "title"),
        ("diagram", "diagram"),
    ]
    assert deck_slide.element("title").text == "My love life"
    assert _diagram(_venn()) == VennDiagram(
        circles=("Things I love", "Things that love me back"), overlap="Cheese", reveal="punchline"
    )
    assert _diagram(_venn(circle_3="Things my cat tolerates")).circles[2] == "Things my cat tolerates"


@pytest.mark.parametrize("circles", [2, 3])
def test_a_venn_diagram_is_drawn_as_see_through_circles_with_their_labels(circles):
    texts = {"circle_3": "Things my cat tolerates"} if circles == 3 else {}
    ppt_slide, shapes, presentation = _drawn(_venn(**texts))
    rings = [shapes[f"Circle {number}"] for number in range(1, circles + 1)]
    labels = [shapes[name] for name in shapes if name.startswith("Circle ") and ":" in name]
    overlap = shapes["Overlap: Cheese"]

    assert len([shape for shape in ppt_slide.shapes if shape.name.startswith("Circle ")]) == 2 * circles
    assert all(ring.width == ring.height == rings[0].width for ring in rings)  # circles, all the same size
    assert {_alpha(ring) for ring in rings} == {round(diagrams.CIRCLE_OPACITY * 100000)}  # see-through
    assert len({str(ring.fill.fore_color.rgb) for ring in rings}) == circles  # each in its own colour
    assert all(ring._element.find(qn("p:style")) is None for ring in rings)  # without the theme's shadow
    assert [_text(label) for label in labels] == list(_diagram(_venn(**texts)).circles)
    for index, label in enumerate(labels):  # in the part of its circle that's its own
        assert _inside(_centre(label), rings[index])
        assert not any(_inside(_centre(label), ring) for ring in rings if ring is not rings[index])
    assert all(_inside(_centre(overlap), ring) for ring in rings)  # the punchline: where they all overlap
    assert overlap.text_frame.paragraphs[0].runs[0].font.bold
    assert _on_the_slide(ppt_slide, presentation)
    # The diagram took the place of the layout's content: no empty placeholder is left
    assert [shape.name for shape in ppt_slide.placeholders] == ["Title 1"]
    assert not any(shape.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.CHART) for shape in ppt_slide.shapes)


def test_a_venn_diagram_takes_two_or_three_circles():
    frame = diagrams.Box(0, 0, 10 * 914400, 5 * 914400)
    for circles in (1, 4):
        with pytest.raises(ValueError):
            diagrams.venn_layout(frame, circles)
    deck_slide = DeckSlide(
        type="diagram",
        layout="classic/diagram",
        elements=(DiagramElement(role="diagram", diagram=VennDiagram(circles=("Alone",), overlap="Me")),),
    )
    with pytest.raises(ValueError):
        render_slide(powerpoint_slide_creator.create_new_powerpoint(), deck_slide)


# 2×2 MATRICES


@pytest.mark.parametrize("quadrant", diagram.QUADRANTS)
def test_a_matrix_puts_its_dot_in_the_planned_quadrant(quadrant):
    for seed in range(5):
        matrix = _diagram(_matrix(seed, dot_quadrant=quadrant))
        assert (matrix.dot_x > 0.5) == quadrant.endswith("right")
        assert (matrix.dot_y > 0.5) == quadrant.startswith("top")
        # Towards its quadrant's outer side, and in the half of it nearer the middle (the label is at its outer edge)
        assert abs(matrix.dot_x - 0.5) >= 0.3 and 0.1 <= abs(matrix.dot_y - 0.5) <= 0.2


def test_a_matrix_without_a_quadrant_for_its_dot_gets_a_random_one():
    corners = set()
    for seed in range(20):
        matrix = _diagram(_matrix(seed, dot_quadrant=None))
        corners.add((matrix.dot_x > 0.5, matrix.dot_y > 0.5))
    assert len(corners) == 4


def test_a_matrix_holds_its_texts():
    matrix = _diagram(_matrix())
    assert (matrix.x_left, matrix.x_right, matrix.y_bottom, matrix.y_top) == (
        "Low effort",
        "High effort",
        "Barely loves you",
        "Loves you a lot",
    )
    assert (matrix.top_left, matrix.top_right, matrix.bottom_left, matrix.bottom_right) == (
        "Dogs",
        "Children",
        "Rocks",
        "Cats",
    )
    assert (matrix.dot, matrix.reveal) == ("My grandmother's parrot", "punchline")


@pytest.mark.parametrize("quadrant", diagram.QUADRANTS)
def test_a_matrix_is_drawn_with_two_axes_four_quadrants_and_a_dot(quadrant):
    ppt_slide, shapes, presentation = _drawn(_matrix(dot_quadrant=quadrant))
    names = ("Top left", "Top right", "Bottom left", "Bottom right")
    quadrants = [shapes[f"{name} quadrant"] for name in names]
    top_left, top_right, bottom_left, bottom_right = quadrants
    # A 2×2 grid, light and see-through
    assert top_left.top == top_right.top and bottom_left.top == bottom_right.top == top_left.top + top_left.height
    assert top_left.left == bottom_left.left and top_right.left == bottom_right.left == top_left.left + top_left.width
    assert {_alpha(shape) for shape in quadrants} == {round(diagrams.QUADRANT_OPACITY * 100000)}
    left, top = top_left.left, top_left.top
    right, bottom = bottom_right.left + bottom_right.width, bottom_right.top + bottom_right.height
    middle_x, middle_y = top_right.left, bottom_left.top

    # The axes cross in the middle, with an arrow at both ends
    across, up = shapes["Axis along the bottom"], shapes["Axis going up"]
    assert (across.begin_y, across.end_y) == (middle_y, middle_y) and across.begin_x < left and across.end_x > right
    assert (up.begin_x, up.end_x) == (middle_x, middle_x) and up.end_y < top and up.begin_y > bottom
    for axis in (across, up):
        outline = axis._element.spPr.find(qn("a:ln"))
        assert [outline.find(qn(end)).get("type") for end in ("a:headEnd", "a:tailEnd")] == ["triangle", "triangle"]

    # A title at each end of the axes, outside the matrix
    assert shapes["Left end: Low effort"].left + shapes["Left end: Low effort"].width < left
    assert shapes["Right end: High effort"].left > right
    assert shapes["Top end: Loves you a lot"].top + shapes["Top end: Loves you a lot"].height < top
    assert shapes["Bottom end: Barely loves you"].top > bottom

    # Every quadrant's label in its quadrant, at its outer edge
    for name, box, label in zip(names, quadrants, ("Dogs", "Children", "Rocks", "Cats"), strict=True):
        text = shapes[f"{name} quadrant: {label}"]
        assert _within(text, box.left, box.top, box.left + box.width, box.top + box.height)
        assert (_centre(text)[1] < _centre(box)[1]) == name.startswith("Top")

    # The dot in its quadrant, its name beside it, in the same quadrant and clear of the quadrant's label
    dot, name = shapes["Dot"], shapes["Dot: My grandmother's parrot"]
    index = diagram.QUADRANTS.index(quadrant)
    box = quadrants[index]
    label = shapes[f"{names[index]} quadrant: {('Dogs', 'Children', 'Rocks', 'Cats')[index]}"]
    for shape in (dot, name):
        assert _within(shape, box.left, box.top, box.left + box.width, box.top + box.height)
    assert name.top >= label.top + label.height or name.top + name.height <= label.top
    assert dot.width == dot.height and str(dot.fill.fore_color.rgb) == "E03C31"
    assert name.text_frame.paragraphs[0].runs[0].font.bold
    assert _on_the_slide(ppt_slide, presentation)
    assert [shape.name for shape in ppt_slide.placeholders] == ["Title 1"]


def test_the_dot_goes_where_the_deck_says():
    layout = diagrams.matrix_layout(diagrams.Box(0, 0, 11 * 914400, 5 * 914400))
    box = layout.matrix
    assert layout.point(0, 0) == (box.left, box.bottom)
    assert layout.point(1, 1) == (box.right, box.top)
    assert layout.point(0.5, 0.5) == box.centre
    # Its name goes on the side with the most room in its quadrant, and stays in the matrix
    for x, y in ((0.05, 0.95), (0.45, 0.55), (0.55, 0.05), (0.98, 0.5)):
        name, _ = diagrams.dot_label_box(layout, x, y)
        assert box.left <= name.left and name.right <= box.right and box.top <= name.top and name.bottom <= box.bottom


def test_the_dots_quadrant_is_one_of_the_options():
    field = next(text for text in KINDS["matrix"].texts if text.name == "dot_quadrant")
    assert clean_text("Top-Right", field) == "top right"
    assert clean_text("bottom_left.", field) == "bottom left"
    assert clean_text("in the middle", field) is None  # and the dot gets a quadrant of its own
    assert 0 <= _diagram(_matrix(dot_quadrant=None)).dot_x <= 1

    properties = prompt.slide_schema(Recipe("matrix"))["properties"]
    assert properties["dot_quadrant"]["enum"] == [*diagram.QUADRANTS, ""]
    assert "enum" not in properties["dot"]
    plan = SlidePlan(kind="matrix", texts={**MATRIX, "dot_quadrant": "in the middle"})
    (warning,) = external.plan_warnings(plan, Recipe("matrix"))
    assert warning.startswith("dot_quadrant is none of 'top left'") and warning.endswith("talkgenerator picked one")


# THE PUNCHLINE, ON A CLICK


def _timing(ppt_slide):
    return ppt_slide.element.find(qn("p:timing"))


@pytest.mark.parametrize(
    ("slide", "punchline"),
    [(_venn(), ["Overlap: Cheese"]), (_matrix(), ["Dot", "Dot: My grandmother's parrot"])],
    ids=["venn", "matrix"],
)
def test_the_punchline_appears_on_a_click(slide, punchline):
    ppt_slide, shapes, _ = _drawn(slide)
    ids = [str(shapes[name].shape_id) for name in punchline]
    assert _timing(ppt_slide) is not None
    timing = ppt_slide.element.xpath  # (the slide's xpath knows PowerPoint's namespaces)
    assert len(timing(".//p:timing//p:cond[@delay='indefinite']")) == 1  # one click
    effects = timing(".//p:timing//p:cTn[@presetClass='entr']")
    assert [effect.get("nodeType") for effect in effects] == ["clickEffect"] + ["withEffect"] * (len(ids) - 1)
    assert {effect.get("presetID") for effect in effects} == {"10"}  # fading in
    assert sorted(set(timing(".//p:timing//p:spTgt/@spid"))) == sorted(ids)
    assert timing(".//p:timing/p:bldLst/p:bldP/@spid") == ids
    tags = [child.tag for child in ppt_slide.element]
    assert tags.index(qn("p:timing")) > tags.index(qn("p:clrMapOvr"))
    numbers = timing(".//p:timing//p:cTn/@id")  # every one of them unique
    assert len(numbers) == len(set(numbers))


def test_a_diagram_that_shows_its_punchline_from_the_start_has_no_animation():
    venn = VennDiagram(circles=("Things I love", "Things that love me back"), overlap="Cheese")  # reveal: all
    ppt_slide, _, _ = _drawn(slides.DiagramSlide("My love life", venn))
    assert _timing(ppt_slide) is None


def test_long_labels_get_smaller_text():
    box = diagrams.Box(0, 0, 2 * 914400, 1 * 914400)
    short = diagrams.fitting_size("Cheese", box, 32, bold=True)
    long = diagrams.fitting_size("Things that love me back when nobody is looking", box, 32, bold=True)
    assert short > long >= 12
    assert diagrams.fitting_size("Supercalifragilisticexpialidocious" * 3, box, 32) == 12  # never smaller


# THE DECK


def _diagram_deck():
    return Deck(
        generator="test",
        title="Cats",
        slides=(_venn().to_deck_slide(), _venn(circle_3="Naps").to_deck_slide(), _matrix().to_deck_slide()),
    )


def _summary(ppt_slide):
    return [
        (
            shape.name,
            shape.left,
            shape.top,
            shape.width,
            shape.height,
            shape.text_frame.text if shape.has_text_frame else None,
        )
        for shape in ppt_slide.shapes
    ]


def test_a_diagram_survives_json_and_renders_from_it():
    deck = _diagram_deck()
    text = deck.to_json()
    assert Deck.from_json(text) == deck
    data = json.loads(text)
    assert [slide["elements"][1]["diagram"]["diagram_type"] for slide in data["slides"]] == ["venn", "venn", "matrix"]
    assert data["slides"][0]["elements"][1]["kind"] == "diagram"

    expected = [
        _summary(slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint()))
        for slide in (_venn(), _venn(circle_3="Naps"), _matrix())
    ]
    presentation = render_pptx(Deck.from_json(text))
    assert [_summary(slide) for slide in presentation.slides] == expected


def test_diagrams_are_strict():
    with pytest.raises(ValidationError):
        VennDiagram(circles=("A", "B"), overlap="C", colour="blue")
    with pytest.raises(ValidationError):
        MatrixDiagram(dot_x=1.5)
    with pytest.raises(ValidationError):
        DiagramElement.model_validate({"role": "diagram", "diagram": {"diagram_type": "pyramid"}})
    with pytest.raises(ValidationError):
        VennDiagram(circles=("A", "B"), overlap="C", reveal="sometimes")
    schema = Deck.json_schema()
    assert {"VennDiagram", "MatrixDiagram", "DiagramElement"} <= set(schema["$defs"])


def test_the_diagram_layout_is_a_classic_layout():
    assert classic.CLASSIC_ROLES["diagram"] == {"title": "title", "diagram": "diagram"}
    assert classic.REQUIRED_ROLES["diagram"] == ("diagram",)
    assert slides.DiagramSlide.required_arguments == ("diagram",)


# THE CHECKS


def _deck_of(*diagrams_):
    return Deck(
        generator="test",
        slides=tuple(
            DeckSlide(
                type="diagram",
                layout="classic/diagram",
                elements=(TextElement(role="title", text="Katten"), DiagramElement(role="diagram", diagram=item)),
            )
            for item in diagrams_
        ),
    )


def _errors(findings):
    return [(finding.slide, finding.message) for finding in findings if finding.severity == "error"]


def test_complete_diagrams_pass_the_checks():
    deck = _diagram_deck()
    assert _errors(check_completeness(deck)) == []
    assert check_leftovers(deck) == []


def test_the_completeness_check_finds_diagrams_with_gaps():
    deck = _deck_of(
        VennDiagram(circles=("Things I love",), overlap="Cheese"),
        VennDiagram(circles=("Things I love", " "), overlap=""),
        MatrixDiagram(x_left="Cheap", x_right="Expensive", y_bottom="Boring", y_top="Fun", top_left="A", top_right="B"),
    )
    assert _errors(check_completeness(deck)) == [
        (1, "a Venn diagram of 1 circle (it takes two or three)"),
        (2, "a Venn diagram with an empty circle 2"),
        (2, "a Venn diagram with an empty overlap"),
        (3, "a 2×2 matrix with an empty bottom left quadrant"),
        (3, "a 2×2 matrix with an empty bottom right quadrant"),
        (3, "a 2×2 matrix with an empty dot"),
    ]

    without = Deck(generator="test", slides=(DeckSlide(type="diagram", layout="classic/diagram"),))
    assert any(finding.message == "no diagram on this diagram slide" for finding in check_completeness(without))


def test_the_leftovers_check_reads_the_labels_of_diagrams():
    deck = _deck_of(VennDiagram(circles=("Things I love", "#animal# things"), overlap="The {seed}"))
    messages = [finding.message for finding in check_leftovers(deck)]
    assert "an unexpanded tracery symbol in its diagram's circle 2: '#animal#'" in messages
    assert "an unfilled template variable in its diagram's overlap: '{seed}'" in messages


def test_the_language_check_reads_the_labels_of_diagrams():
    english = VennDiagram(circles=("Things that are in the house", "Things that are on the roof"), overlap="The cat")
    deck = _deck_of(english).model_copy(update={"language": "nl"})
    assert "reads as English, not Dutch" in [finding.message for finding in check_language(deck)]
    dutch = VennDiagram(circles=("Dingen in het huis", "Dingen op het dak"), overlap="De kat")
    assert check_language(_deck_of(dutch).model_copy(update={"language": "nl"})) == []


# PLANNED SLIDES


def test_a_planned_venn_diagram_comes_out_as_planned():
    plan = SlidePlan(kind="venn", concept="cheese", texts={**VENN, "overlap": ' "Cheese" '})
    realized = realize(plan, Recipe("venn"), {"seed": "cheese", "topic": "love"}, random_util.Rng(3), 0)
    assert realized is not None
    slide, generated = realized
    assert _diagram(slide).overlap == "Cheese"  # without its quote marks
    assert "Cheese" in generated and "Things I love" in generated
    assert external.plan_warnings(plan, Recipe("venn")) == []


def test_a_planned_matrix_without_a_dot_cant_be_made():
    plan = SlidePlan(kind="matrix", concept="pets", texts={**MATRIX, "dot": ""})
    problems = []
    assert realize(plan, Recipe("matrix"), {"seed": "pets"}, random_util.Rng(4), 0, problems=problems) is None
    assert problems == ["dot: not written"]


# THE CLASSIC DIAGRAMS


@pytest.fixture
def words(monkeypatch):
    """Fake word sources: what describes a word, what's related to it, and its opposites."""
    properties = {
        "cat": [(1.0, "fluffy"), (0.9, "day"), (0.8, "evil"), (0.7, "catlike"), (0.6, "lazy"), (0.5, "fluffy")],
        "travel": [(1.0, "international"), (0.5, "safe")],
    }
    related = {"cat": [(1.0, "dog"), (0.9, "mouse"), (0.8, "cat food"), (0.7, "yarn"), (0.6, "milk"), (0.5, "lazy")]}
    opposites = {"fluffy": [(1.0, "bald")]}
    monkeypatch.setattr(conceptnet, "get_weighted_properties", lambda word: properties.get(word, []))
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: related.get(word, []))
    monkeypatch.setattr(conceptnet, "get_weighted_antonyms", lambda word: opposites.get(word, []))
    monkeypatch.setattr(diagram, "venn_title_generator", lambda context: f"The {context['seed']} paradox")
    monkeypatch.setattr(diagram, "matrix_title_generator", lambda context: f"The {context['seed']} matrix")
    return properties


def test_the_classic_venn_diagram(words):
    found = set()
    for seed in range(12):
        with random_util.use(random_util.Rng(seed)):
            title, venn = diagram.generate_venn({"seed": "cat", "topic": "pets"})
        assert title == "The cat paradox"
        assert venn.overlap == "Cat" and venn.reveal == "punchline"
        assert len(venn.circles) in (2, 3) and len(set(venn.circles)) == len(venn.circles)
        found |= {circle.lower() for circle in venn.circles}
    # From what describes the seed: not "day" (no adjective), "catlike" (holds the seed), nor "fluffy" twice
    assert any("fluffy" in circle for circle in found) and any("lazy" in circle for circle in found)
    assert not any("day" in circle or "catlike" in circle for circle in found)
    with random_util.use(random_util.Rng(7)):
        sizes = {len(diagram.generate_venn({"seed": "cat"})[1].circles) for _ in range(30)}
    assert sizes == {2, 3}  # three circles a third of the time


def test_a_classic_venn_diagram_of_more_words_falls_back_on_the_last_one(words):
    with random_util.use(random_util.Rng(1)):
        title, venn = diagram.generate_venn({"seed": "time travel"})
    assert {circle.lower() for circle in venn.circles} <= {
        f"{form.format(word)}".lower() for form in diagram._CIRCLE_FORMS for word in ("international", "safe")
    }
    assert venn.overlap == "Time travel"


def test_a_classic_diagram_needs_words_to_be_made(words):
    words["cat"] = [(1.0, "fluffy")]
    assert diagram.generate_venn({"seed": "cat"}) is None
    assert diagram.generate_matrix({"seed": "cat"}) is None
    assert diagram.generate_venn({"seed": "nothing"}) is None


def test_the_classic_matrix(words):
    with random_util.use(random_util.Rng(2)):
        title, matrix = diagram.generate_matrix({"seed": "cat", "topic": "pets"})
    assert title == "The cat matrix"
    ends = {(matrix.x_left, matrix.x_right), (matrix.y_bottom, matrix.y_top)}
    # Two of the words that describe the seed, from their opposite (or from "Not") to themselves (or "Very")
    assert ends <= {("Bald", "Fluffy"), ("Not evil", "Very evil"), ("Not lazy", "Very lazy")} and len(ends) == 2
    quadrants = {matrix.top_left, matrix.top_right, matrix.bottom_left, matrix.bottom_right}
    assert quadrants == {"Dog", "Mouse", "Yarn", "Milk"}  # related, but not the seed, nor what describes it
    assert matrix.dot == "Cat" and matrix.reveal == "punchline"
    assert abs(matrix.dot_x - 0.5) >= 0.3 and 0.1 <= abs(matrix.dot_y - 0.5) <= 0.2


@pytest.mark.parametrize("generate", [diagram.generate_venn, diagram.generate_matrix], ids=["venn", "matrix"])
def test_a_classic_diagram_makes_a_slide(words, generate):
    generator = SlideGeneratorData(slide_generator_types.DiagramSlideGenerator(generate), retries=1, name="Diagram")
    with random_util.use(random_util.Rng(5)):
        result = generator.generate({"seed": "cat", "topic": "pets"}, set())
    assert result is not None
    slide, generated = result
    assert isinstance(slide, slides.DiagramSlide)
    assert slide.missing_content() == []
    assert set(generated)  # the slide's content can be compared with what other slides used
    deck_slide = slide.to_deck_slide()
    assert deck_slide.type == "diagram" and deck_slide.element("title").text.startswith("The cat")
    assert check_completeness(Deck(generator="test", slides=(deck_slide,)))[1:] == []


# THE FORMATS


@pytest.mark.parametrize("format_name", ["default", "ted"])
def test_every_format_has_diagrams_but_not_too_many(format_name):
    schema = get_schema(format_name)
    names = {generator.name: generator for generator in schema.slide_generators}
    assert names["Venn Diagram"].llm.kind == "venn"
    assert names["2x2 Matrix"].llm.kind == "matrix"
    assert schema._max_allowed_tags["venn_diagram"] == 1
    assert schema._max_allowed_tags["matrix_diagram"] == 1
    choices = external.recipes_of(schema)
    assert external.default_recipe(choices, "venn").id == "venn-diagram"
    assert external.default_recipe(choices, "matrix").id == "2x2-matrix"


def test_the_reference_lists_the_diagrams():
    reference = external.catalog_markdown("ted")
    assert "## `venn`" in reference and "## `matrix`" in reference and "`bottom right`" in reference
    (matrix,) = [kind for kind in external.catalog("ted")["kinds"] if kind["kind"] == "matrix"]
    assert {text["name"]: text.get("options") for text in matrix["texts"]}["dot_quadrant"] == list(diagram.QUADRANTS)
