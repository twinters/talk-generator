"""Offline tests of the deck format: talks as plain data, which the PowerPoint renderer draws.

A slide drawn from its deck form has to look exactly like the slide v4 drew straight from its arguments, and a deck
has to survive a trip through JSON.
"""

import io
import json

import pytest
from PIL import Image
from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE
from pydantic import ValidationError

from talkgenerator import generator
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.deck import ChartSeries, ChartSpec, Deck, DeckSlide, ImageAsset, ImageElement, TextElement
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_pptx, render_slide
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import image_util


def _jpeg(size):
    output = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(output, "JPEG")
    return output.getvalue()


@pytest.fixture
def images(monkeypatch):
    """Serve fake images: a landscape one, a portrait one and a square one. Local files (such as the template's
    overlay for quote slides) load as usual."""
    served = {
        "https://example.com/wide.jpg": _jpeg((400, 300)),
        "https://example.com/tall.jpg": _jpeg((300, 400)),
        "https://example.com/square.jpg": _jpeg((300, 300)),
    }
    downloads = []
    load = image_util.fetch_image

    def fetch(url):
        if not url.startswith("http"):
            return load(url)
        downloads.append(url)
        return served.get(url)

    monkeypatch.setattr(image_util, "fetch_image", fetch)
    return downloads


def _image(name, source="Test"):
    return ImageData(f"https://example.com/{name}.jpg", source=source, source_url=f"https://example.com/{name}")


def _pie_chart_data():
    data = ChartData()
    data.categories = ["Yes", "No", "Only on Tuesdays"]
    data.add_series("", [0.2, 0.3, 0.5])
    return data


def _scatter_chart_data():
    data = XyChartData()
    series = data.add_series("Model")
    for x, y in [(1.0, 2.0), (2.0, 3.5), (3.0, 1.25)]:
        series.add_data_point(x, y)
    return data


def _every_kind_of_slide():
    """One slide of every classic type, with images, text in an image slot, both image fits, credits and charts."""
    credited = slides.ImageSlide("Cats", _image("wide"))
    credited.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    credited.add_source("u/bob (on r/pics)", None)
    return [
        slides.TitleSlide("A talk about cats", "By An O. Nymous"),
        slides.LarqeQuoteSlide(None, "Be brave, little cat", background_image=_image("wide")),
        credited,
        slides.ImageSlide(None, _image("tall"), original_image_size=False),
        slides.FullImageSlide("Look at this", _image("square")),
        slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", "A quote where a picture goes"),
        slides.ThreeColumnImageSlide(
            None, "One", _image("wide"), "Two", _image("tall"), "Three", _image("square"), original_image_size=False
        ),
        slides.ChartSlide("Do cats like Mondays?", XL_CHART_TYPE.PIE, _pie_chart_data(), None),
        slides.ChartSlide("Who likes bread?", XL_CHART_TYPE.DOUGHNUT, _pie_chart_data(), None),
        slides.ChartSlide("Cat growth", XL_CHART_TYPE.COLUMN_CLUSTERED, _pie_chart_data(), None),
        slides.ChartSlide("Cats versus time", XL_CHART_TYPE.XY_SCATTER, _scatter_chart_data(), None),
    ]


_V4_STYLES = {
    XL_CHART_TYPE.PIE: charts.set_pie_properties,
    XL_CHART_TYPE.DOUGHNUT: charts.set_doughnut_properties,
    XL_CHART_TYPE.COLUMN_CLUSTERED: charts.set_histogram_properties,
    XL_CHART_TYPE.XY_SCATTER: charts.set_scatter_properties,
}


def _draw_like_v4(slide, presentation):
    """What Slide.create_powerpoint_slide did in v4: call the slide's creator with its arguments, then credit it."""
    arguments = dict(slide._arguments)
    if slide.type_name == "chart":
        arguments["chart_modifier"] = _V4_STYLES[arguments["chart_type"]]
    ppt_slide = slide._ppt_slide_creator(presentation, **arguments)
    if slide._credits:
        powerpoint_slide_creator.add_sources_note(ppt_slide, slide._credits)
    powerpoint_slide_creator.remove_empty_placeholders(ppt_slide)
    return ppt_slide


def _summary(ppt_slide):
    """What a slide shows: its shapes, their texts and links, pictures with their crops, and charts with their data."""
    shapes = []
    for shape in ppt_slide.shapes:
        entry = {
            "type": shape.shape_type,
            "placeholder": shape.placeholder_format.idx if shape.is_placeholder else None,
            "position": (shape.left, shape.top, shape.width, shape.height),
        }
        if shape.has_text_frame:
            entry["runs"] = [
                (run.text, run.hyperlink.address) for paragraph in shape.text_frame.paragraphs for run in paragraph.runs
            ]
        image = getattr(shape, "image", None)
        if image is not None:
            entry["image"] = image.sha1
            entry["crop"] = (shape.crop_left, shape.crop_right, shape.crop_top, shape.crop_bottom)
        if shape.has_chart:
            plot = shape.chart.plots[0]
            entry["chart"] = (
                shape.chart.chart_type,
                list(plot.categories),
                [list(series.values) for series in plot.series],
                [label.text_frame.text for label in _data_labels(plot)],
            )
        shapes.append(entry)
    return shapes


def _data_labels(plot):
    if plot.chart.chart_type == XL_CHART_TYPE.XY_SCATTER or not plot.has_data_labels:
        return []  # python-pptx can't read the labels of scatter plots (and the classic ones have none)
    return [point.data_label for series in plot.series for point in series.points]


@pytest.mark.parametrize("index", range(len(_every_kind_of_slide())))
def test_a_slide_drawn_from_the_deck_looks_like_v4_drew_it(images, index):
    v4_slide = _every_kind_of_slide()[index]
    deck_slide = _every_kind_of_slide()[index]

    expected = _summary(_draw_like_v4(v4_slide, powerpoint_slide_creator.create_new_powerpoint()))
    drawn = deck_slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())

    assert _summary(drawn) == expected


def test_slides_become_elements_with_roles(images):
    deck_slide = slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", "Text").to_deck_slide()

    assert deck_slide.type == "two_column_image"
    assert deck_slide.layout == "classic/two_column_image"
    assert [(element.kind, element.role) for element in deck_slide.elements] == [
        ("text", "title"),
        ("text", "caption_1"),
        ("image", "content_1"),
        ("text", "caption_2"),
        ("text", "content_2"),
    ]
    image = deck_slide.element("content_1")
    assert isinstance(image, ImageElement)
    assert image.image.url == "https://example.com/wide.jpg"
    assert [(part.text, part.url) for part in image.image.credit] == [("Test", "https://example.com/wide")]


def test_empty_content_and_image_fits(images):
    quote = slides.LarqeQuoteSlide(None, "Be brave", background_image=_image("wide")).to_deck_slide()
    assert [element.role for element in quote.elements] == ["text", "background"]
    assert quote.element("background").fit == "cover"
    assert slides.ImageSlide("  ", _image("tall")).to_deck_slide().element("title") is None
    assert slides.ImageSlide(None, _image("tall"), original_image_size=False).to_deck_slide().element(
        "content"
    ).fit == ("cover")
    # A caption that looks like a file name is still a caption
    assert slides.TwoColumnImageSlide(None, "cat.jpg").to_deck_slide().element("caption_1").kind == "text"


def _deck_of_every_kind_of_slide():
    deck = SlideDeck(len(_every_kind_of_slide()), title="Cats", topics=["cat", "dog"], presenter="Ann", seed=3)
    for index, slide in enumerate(_every_kind_of_slide()):
        deck.add_slide(index, slide)
    return deck


def test_a_deck_survives_json(images):
    deck = _deck_of_every_kind_of_slide().to_deck(schema_name="default")
    text = deck.to_json()

    assert Deck.from_json(text) == deck
    assert deck.to_json() == text  # the same deck always gives the same JSON
    data = json.loads(text)
    assert data["deck_version"] == 1
    assert data["generator"].startswith("talkgenerator ")
    assert (data["title"], data["topics"], data["presenter"], data["seed"]) == ("Cats", ["cat", "dog"], "Ann", 3)
    assert data["schema_name"] == "default"
    assert [slide["type"] for slide in data["slides"]][:3] == ["title", "large_quote", "image"]


def test_a_deck_from_json_renders_without_the_generation_run(images):
    """A saved deck renders on its own: images get downloaded again, and it looks the same."""
    slide_deck = _deck_of_every_kind_of_slide()
    expected = [
        _summary(slide) for slide in slide_deck.save_to_powerpoint(powerpoint_slide_creator.create_new_powerpoint())
    ]

    downloads_before = len(images)
    presentation = render_pptx(Deck.from_json(slide_deck.to_deck().to_json()))

    assert [_summary(slide) for slide in presentation.slides] == expected
    assert len(images) > downloads_before


def test_the_images_checked_while_generating_are_reused(images):
    image = _image("wide")
    assert image_util.fetch_image_data(image) is not None  # checked while generating
    slide = slides.ImageSlide("Cats", image)
    downloads_before = len(images)

    slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())

    assert len(images) == downloads_before


def test_chart_data_round_trip():
    pie = charts.chart_spec(XL_CHART_TYPE.PIE, _pie_chart_data())
    assert pie == ChartSpec(
        chart_type="pie",
        categories=("Yes", "No", "Only on Tuesdays"),
        series=(ChartSeries(values=(0.2, 0.3, 0.5)),),
    )
    chart_type, data = charts.pptx_chart_data(pie)
    assert chart_type == XL_CHART_TYPE.PIE
    assert [category.label for category in data.categories] == ["Yes", "No", "Only on Tuesdays"]
    assert [list(series.values) for series in data] == [[0.2, 0.3, 0.5]]

    scatter = charts.chart_spec(XL_CHART_TYPE.XY_SCATTER, _scatter_chart_data())
    assert scatter.series == (ChartSeries(name="Model", points=((1.0, 2.0), (2.0, 3.5), (3.0, 1.25))),)
    assert charts.pptx_chart_data(scatter)[0] == XL_CHART_TYPE.XY_SCATTER


def test_numbers_json_cant_hold_become_zero():
    data = ChartData()
    data.categories = ["a", "b"]
    data.add_series("", [float("inf"), float("nan")])
    assert charts.chart_spec(XL_CHART_TYPE.PIE, data).series[0].values == (0.0, 0.0)


def test_unsupported_charts_are_refused():
    with pytest.raises(ValueError):
        charts.chart_spec(XL_CHART_TYPE.LINE, _pie_chart_data())


def test_the_slide_deck_dictionary_is_json():
    deck = SlideDeck(1)
    deck.add_slide(0, slides.TitleSlide("Cats", None))
    assert json.loads(json.dumps(deck.to_slide_deck_dictionary())) == [
        {
            "type": "title",
            "layout": "classic/title",
            "elements": [{"kind": "text", "role": "title", "text": "Cats"}],
            "credits": [],
            "notes": "",
        }
    ]


def test_decks_are_strict():
    with pytest.raises(ValidationError):
        Deck(generator="test", colour="blue")
    with pytest.raises(ValidationError):
        Deck.from_json('{"deck_version": 2, "generator": "a future version"}')
    assert "deck_version" in Deck.json_schema()["properties"]


def test_the_renderer_refuses_what_it_cant_draw():
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    with pytest.raises(ValueError):
        render_slide(presentation, DeckSlide(type="image", layout="neon/image"))
    with pytest.raises(ValueError):
        render_slide(presentation, DeckSlide(type="hologram", layout="classic/hologram"))
    with pytest.raises(ValueError):
        render_slide(
            presentation,
            DeckSlide(type="title", layout="classic/title", elements=(TextElement(role="footnote", text="Hi"),)),
        )
    with pytest.raises(ValueError):
        render_pptx(Deck(generator="test", theme="neon"))


def test_images_without_a_store_keep_their_credit(images):
    deck_slide = DeckSlide(
        type="image",
        layout="classic/image",
        elements=(ImageElement(role="content", image=ImageAsset(url="https://example.com/wide.jpg")),),
        credits=(),
    )
    assert render_slide(powerpoint_slide_creator.create_new_powerpoint(), deck_slide) is not None


def test_save_deck_to_json(tmp_path):
    deck = Deck(generator="test", title="Cats")

    next_to = generator.save_deck_to_json(deck, str(tmp_path), "cats", next_to=str(tmp_path / "cats_2.pptx"))
    assert next_to == str(tmp_path / "cats_2.json")
    assert Deck.from_json((tmp_path / "cats_2.json").read_text(encoding="utf-8")) == deck

    first = generator.save_deck_to_json(deck, str(tmp_path / "decks"), "cats")
    second = generator.save_deck_to_json(deck, str(tmp_path / "decks"), "cats")
    assert (first, second) == (str(tmp_path / "decks" / "cats.json"), str(tmp_path / "decks" / "cats_1.json"))


def test_cli_flag():
    parser = generator.get_argument_parser()
    assert parser.parse_args(["--topic", "cat"]).save_json is False
    assert parser.parse_args(["--topic", "cat", "--save_json", "true"]).save_json is True
