"""Offline tests of the deck format: talks as plain data, which the PowerPoint renderer draws.

A slide drawn from its deck form has to look exactly like the slide v4 drew straight from its arguments, and a deck
has to survive a trip through JSON.
"""

import io
import json

import pytest
from PIL import Image
from pptx import Presentation
from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE
from pydantic import ValidationError

from talkgenerator import generator
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, themes
from talkgenerator.models.deck import (
    DECORATION,
    ChartSeries,
    ChartSpec,
    Deck,
    DeckSlide,
    ImageAsset,
    ImageElement,
    ShapeElement,
    TextElement,
)
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_pptx, render_slide
from talkgenerator.render.shapes import EMU_PER_PIXEL
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import image_util, os_util, random_util


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
        for v5_only in ("x_title", "y_title", "reveal", "point_labels"):  # axis titles, animations, named points: v5
            arguments.pop(v5_only, None)
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
        charts.chart_spec(XL_CHART_TYPE.RADAR, _pie_chart_data())


def test_the_slide_deck_dictionary_is_json():
    deck = SlideDeck(1)
    deck.add_slide(0, slides.TitleSlide("Cats", None))
    with pytest.warns(DeprecationWarning, match=r"Use slide_deck\.to_deck\(\) instead"):  # (see test_deprecations)
        dictionary = deck.to_slide_deck_dictionary()
    assert json.loads(json.dumps(dictionary)) == [
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


# Pictures wider and narrower than every frame of the template's: the full picture's is 16:9, the title and
# picture's about 1.92:1, a column's about 1.12:1 out of two and 0.76:1 out of three
_PICTURE_SIZES = {
    "panorama_3x1": (900, 300),
    "widescreen_16x9": (1600, 900),
    "landscape_4x3": (400, 300),
    "square": (300, 300),
    "portrait_3x4": (300, 400),
    "portrait_9x16": (900, 1600),
}
_PICTURE_ROLES = {
    "image": ("content",),
    "full_image": ("content",),
    "two_column_image": ("content_1", "content_2"),
    "three_column_image": ("content_1", "content_2", "content_3"),
}


@pytest.mark.parametrize("size", _PICTURE_SIZES.values(), ids=_PICTURE_SIZES.keys())
@pytest.mark.parametrize("slide_type", _PICTURE_ROLES)
def test_pictures_shown_whole_keep_their_shape(slide_type, size):
    """A picture shown whole (fit "contain") is drawn as large as it fits in its frame, centred, and neither stretched
    nor squashed. v4 padded it by the difference between its aspect ratio and its frame's, which only kept square
    pictures in shape: a 9:16 one on a full-picture slide came out 43% too wide."""
    images = {}
    for role in _PICTURE_ROLES[slide_type]:
        image = ImageData(f"https://example.com/{role}.jpg")
        image.data = _jpeg(size)
        images[role] = image
    deck_slide = DeckSlide(
        type=slide_type,
        layout=f"classic/{slide_type}",
        elements=tuple(
            ImageElement(role=role, image=ImageAsset(url=image.get_image_url()), fit="contain")
            for role, image in images.items()
        ),
    )

    ppt_slide = render_slide(
        powerpoint_slide_creator.create_new_powerpoint(),
        deck_slide,
        images={image.get_image_url(): image for image in images.values()},
    )

    pictures = [shape for shape in ppt_slide.shapes if getattr(shape, "image", None) is not None]
    assert len(pictures) == len(images)
    for picture in pictures:
        # Crops are fractions of the image (negative ones pad it), and what's left of it is stretched over the frame
        drawn_width = picture.width / (1 - picture.crop_left - picture.crop_right)
        drawn_height = picture.height / (1 - picture.crop_top - picture.crop_bottom)
        assert drawn_width / drawn_height == pytest.approx(size[0] / size[1], rel=1e-4)
        # As wide or as high as the frame, and no larger than it either way
        assert max(drawn_width / picture.width, drawn_height / picture.height) == pytest.approx(1, rel=1e-4)
        assert (picture.crop_left, picture.crop_top) == (picture.crop_right, picture.crop_bottom)


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


# THE COLUMNS' ANIMATION


_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def _steps(ppt_slide, name=lambda shape: shape.name):
    """A slide's clicks: per click, what each effect does (appear, dim, play) to which shape (by its name, or by what
    name says of it)."""
    names = {str(shape.shape_id): name(shape) for shape in ppt_slide.shapes}
    timing = ppt_slide.element.find(_P + "timing")
    assert timing is not None
    targets = [target.get("spid") for target in timing.iter(_P + "spTgt")]
    assert all(spid in names for spid in targets)  # (nothing animates a shape the slide doesn't have)
    # The build list says how the slide's own shapes with text build, those whose paragraphs the effects name
    texts = {
        str(shape.shape_id) for shape in ppt_slide.shapes if shape.element.tag == _P + "sp" and shape.has_text_frame
    }
    builds = {build.get("spid") for build in timing.iter(_P + "bldP")}
    assert builds <= texts
    by_paragraph = {target.get("spid") for target in timing.iter(_P + "spTgt") if target.find(_P + "txEl") is not None}
    assert by_paragraph <= builds
    ids = [node.get("id") for node in timing.find(_P + "tnLst").iter(_P + "cTn")]
    assert len(ids) == len(set(ids))
    sequence = timing.find(f".//{_P}cTn[@nodeType='mainSeq']/{_P}childTnLst")
    kinds = {"entr": "appear", "emph": "dim", "mediacall": "play"}
    return [
        [
            (kinds[node.get("presetClass")], names[node.find(f".//{_P}spTgt").get("spid")])
            for node in step.iter(_P + "cTn")
            if node.get("presetClass")
        ]
        for step in sequence.findall(_P + "par")
    ]


def test_columns_appear_click_by_click_the_one_before_dimming(images):
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    three = slides.ThreeColumnImageSlide(
        "Cats", "One", _image("wide"), "Two", _image("tall"), "Three", _image("square")
    ).create_powerpoint_slide(presentation)
    two = slides.TwoColumnImageSlide(
        "Cats", "Expectation", _image("wide"), "Reality", _image("tall")
    ).create_powerpoint_slide(presentation)

    assert _steps(three) == [
        [("appear", "Picture Placeholder 4"), ("appear", "Text Placeholder 2")],
        [
            ("appear", "Picture Placeholder 5"),
            ("appear", "Text Placeholder 3"),
            ("dim", "Picture Placeholder 4"),
            ("dim", "Text Placeholder 2"),
        ],
        [
            ("appear", "Picture Placeholder 7"),
            ("appear", "Text Placeholder 6"),
            ("dim", "Picture Placeholder 5"),
            ("dim", "Text Placeholder 3"),
        ],
    ]
    # The first column shows from the start; the second appears on the click, as the first dims
    assert [[what for what, _ in step] for step in _steps(two)] == [["appear", "appear", "dim", "dim"]]
    # The layouts play nothing themselves (PowerPoint would play theirs before the slide's own)
    assert all(layout.element.find(_P + "timing") is None for layout in presentation.slide_layouts)


def test_a_column_without_its_caption_still_appears(images):
    ppt_slide = slides.ThreeColumnImageSlide(
        None, "One", _image("wide"), None, _image("tall"), "Three", _image("square")
    ).create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())

    steps = _steps(ppt_slide)
    assert [len(step) for step in steps] == [2, 3, 3]  # (the second caption's appearing and dimming are gone)
    assert ("appear", "Picture Placeholder 5") in steps[1]


def test_a_deck_of_column_slides_saves_and_opens_again(images, tmp_path):
    slide_deck = SlideDeck(2, title="Cats")
    slide_deck.add_slide(0, slides.TwoColumnImageSlide("Cats", "A", _image("wide"), "B", _image("tall")))
    slide_deck.add_slide(
        1, slides.ThreeColumnImageSlide(None, "1", _image("wide"), "2", _image("tall"), "3", _image("square"))
    )
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    slide_deck.save_to_powerpoint(presentation)
    presentation.save(tmp_path / "columns.pptx")

    reopened = Presentation(str(tmp_path / "columns.pptx"))
    assert all(slide.element.find(_P + "timing") is not None for slide in list(reopened.slides)[-2:])


def _role(shape, deck_slide):
    """The role of the column's element a shape of a themed slide is drawn for (the one in whose box its middle is),
    or else its name."""
    x = (shape.left + shape.width / 2) / EMU_PER_PIXEL
    y = (shape.top + shape.height / 2) / EMU_PER_PIXEL
    for element in deck_slide.elements:
        box = element.box
        if element.role.startswith(("content_", "caption_")) and box.x <= x <= box.x + box.w:
            if box.y <= y <= box.y + box.h:
                return element.role
    return shape.name


def test_themed_columns_appear_click_by_click_too(images):
    """In every layout for columns, and every theme family (some frame their pictures as polaroids, with grain on
    them, say), the columns appear as the 2019 template's do, each with all it's drawn with."""
    families = list(themes.FAMILIES)
    layouts = set()
    for seed in range(12):
        three_columns = slides.ThreeColumnImageSlide(
            "Cats", "One", _image("wide"), "Two", _image("tall"), "Three", _image("square")
        )
        two_columns = slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", _image("tall"))
        slide_deck = SlideDeck(2, title="Cats", seed=seed)
        for index, slide in enumerate((three_columns, two_columns)):
            slide.add_source("Test", "https://example.com")  # (a credits line, which stays as it is)
            slide_deck.add_slide(index, slide)
        slide_deck.theme = themes.pick(families[seed % len(families)], random_util.Rng(seed))
        deck = slide_deck.to_deck()
        output = io.BytesIO()
        render_pptx(deck, images=slide_deck.image_store()).save(output)
        three, two = Presentation(output).slides  # (saved and opened again)

        for deck_slide, ppt_slide in ((deck.slides[0], three), (deck.slides[1], two)):
            layouts.add(deck_slide.layout)
            clicks = [
                ({role for what, role in step if what == "appear"}, {role for what, role in step if what == "dim"})
                for step in _steps(ppt_slide, lambda shape, deck_slide=deck_slide: _role(shape, deck_slide))
            ]
            first, second, third = ({f"content_{index}", f"caption_{index}"} for index in (1, 2, 3))
            if deck_slide.type == "three_column_image":  # each on a click, the one before dimming
                assert clicks == [(first, set()), (second, first), (third, second)], deck_slide.layout
            else:  # the first from the start, the second on the click, as the first dims
                assert clicks == [(second, first)], deck_slide.layout
            # Everything but the title, the credits and the theme's own shapes and texts (its decoration, a band, a
            # panel, a slide's number)
            animated = {target.get("spid") for target in ppt_slide.element.iter(_P + "spTgt")}
            still = [shape for shape in ppt_slide.shapes if str(shape.shape_id) not in animated]
            shapes = sum(
                isinstance(element, ShapeElement) or element.role == DECORATION for element in deck_slide.elements
            )
            assert len(still) == shapes + 2, (deck_slide.layout, [shape.name for shape in still])
            entrances = ppt_slide.element.xpath(".//p:timing//p:cTn[@presetClass='entr']/@presetID")
            assert set(entrances) == {"10"}  # (fading in)
    assert layouts == {name for name in engine.layout_names() if name.startswith("v5/columns-")}


def test_a_deck_says_how_a_browser_may_show_its_images(images):
    slide = slides.TwoColumnImageSlide(
        "Cats",
        "Online",
        ImageData("https://example.com/wide.jpg", display="copy"),
        "Ours",
        os_util.to_actual_file("data/images/black-transparent.png"),  # (a file of talkgenerator's own)
    )
    online, ours = (element.image for element in slide.to_deck_slide().elements if isinstance(element, ImageElement))
    assert (online.display, ours.display) == ("copy", "local")
    assert ImageAsset(url="https://example.com/x.jpg").display == "direct"
    assert '"display": "copy"' in Deck(generator="test", slides=(slide.to_deck_slide(),)).to_json()
