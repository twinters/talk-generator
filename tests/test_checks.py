"""Offline tests of the automated checks: findings on hand-made decks, and benchmark runs with fake sources."""

import json
import sys

import pytest

from talkgenerator import generator, run
from talkgenerator.checks import benchmark
from talkgenerator.checks.deck import Finding, check_completeness, check_deck, check_images, check_leftovers
from talkgenerator.models import classic
from talkgenerator.models.deck import (
    ChartElement,
    ChartSeries,
    ChartSpec,
    CreditPart,
    Deck,
    DeckSlide,
    ImageAsset,
    ImageElement,
    TextElement,
)
from talkgenerator.slide import slides
from tests import test_seeds


def _text(role, text):
    return TextElement(role=role, text=text)


def _image(role, url="https://example.com/cat.jpg", credit=(CreditPart(text="Ann"),)):
    return ImageElement(role=role, image=ImageAsset(url=url, credit=credit))


def _chart(categories=("Yes", "No"), values=(0.4, 0.6)):
    series = (ChartSeries(values=values),) if values else ()
    return ChartElement(role="chart", chart=ChartSpec(chart_type="pie", categories=categories, series=series))


def _slide(slide_type, *elements):
    return DeckSlide(type=slide_type, layout=classic.layout_id(slide_type), elements=elements)


def _deck(*deck_slides):
    return Deck(generator="test", slides=deck_slides)


TITLE = _slide("title", _text("title", "Cats"), _text("subtitle", "By Ann"))


# CHECKS OF A DECK


def test_a_good_deck_has_no_findings():
    deck = _deck(
        TITLE,
        _slide(
            "two_column_image",
            _text("caption_1", "Before"),
            _image("content_1"),
            _text("caption_2", "After"),
            _image("content_2", "https://example.com/dog.jpg"),
        ),
        _slide("chart", _text("title", "Do cats dream?"), _chart()),
    )
    assert check_deck(deck, expected_slides=3) == []


def test_completeness():
    findings = check_completeness(
        _deck(
            _slide("image", _text("title", "No picture")),
            _slide("large_quote", _text("text", " "), _image("background")),
            _slide("chart", _chart(values=())),
            _slide("hologram"),
        ),
        expected_slides=5,
    )
    assert [(finding.severity, finding.slide, finding.message) for finding in findings] == [
        ("error", None, "4 of the 5 slides"),
        ("warning", 1, "the first slide isn't the title but a slide of type image"),
        ("error", 1, "no content on this image slide"),
        ("error", 2, "an empty text"),
        ("error", 3, "a chart without data"),
        ("error", 4, "an unknown type of slide: 'hologram'"),
    ]


@pytest.mark.parametrize(
    "text, what",
    [
        ("About {seed.plural}", "an unfilled template variable"),
        ("The #adjective# truth", "an unexpanded tracery symbol"),
        ("((hobby)) is fun", "a missing tracery symbol"),
        ("<built-in method title of str object at 0x0000>", "Python code"),
        ("ImageData(https://example.com/1.jpg)", "a Python object"),
    ],
)
def test_template_leftovers_are_errors(text, what):
    (finding,) = check_leftovers(_deck(_slide("title", _text("title", text))))
    assert (finding.severity, finding.slide, finding.check) == ("error", 1, "leftovers")
    assert finding.message.startswith(what)


def test_none_is_suspicious_but_not_always_wrong():
    def severities(text):
        return [finding.severity for finding in check_leftovers(_deck(_slide("title", _text("title", text))))]

    assert severities("About None") == ["warning"]
    assert severities("None") == ["warning"]
    assert severities("None of us were ready") == []


def test_chart_labels_are_checked_too():
    (finding,) = check_leftovers(_deck(_slide("chart", _text("title", "Hm"), _chart(categories=("Yes", "{answer}")))))
    assert "chart label" in finding.message


def test_images_should_be_credited_and_not_come_back():
    findings = check_images(
        _deck(
            _slide("image", _image("content", credit=())),
            _slide("image", _image("content")),
            _slide("image", _image("content", url="C:/Users/me/my photo.jpg", credit=())),  # the user's own
        )
    )
    assert [(finding.slide, finding.message) for finding in findings] == [
        (1, "an image without a credit: https://example.com/cat.jpg"),
        (2, "the same image as slide 1"),
    ]
    assert all(finding.severity == "warning" for finding in findings)


def test_the_required_roles_are_what_the_slide_classes_require():
    types = {
        slides.TitleSlide: "title",
        slides.LarqeQuoteSlide: "large_quote",
        slides.ImageSlide: "image",
        slides.FullImageSlide: "full_image",
        slides.TwoColumnImageSlide: "two_column_image",
        slides.ThreeColumnImageSlide: "three_column_image",
        slides.ChartSlide: "chart",
    }
    assert set(types.values()) == set(classic.REQUIRED_ROLES) == set(classic.CLASSIC_ROLES)
    for slide_class, slide_type in types.items():
        roles = classic.CLASSIC_ROLES[slide_type]
        # A chart's type and data make one chart element
        required = {roles.get(argument, "chart") for argument in slide_class.required_arguments}
        assert required == set(classic.REQUIRED_ROLES[slide_type]), slide_type


# BENCHMARK RUNS


@pytest.fixture
def fake_schema(monkeypatch):
    schema = test_seeds.fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def test_a_benchmark_run_checks_every_talk(fake_schema):
    report = benchmark.run(["cat", "dog"], [1, 2], schema="fake", slides=test_seeds.NUM_SLIDES)

    summary = report["summary"]
    assert (summary["talks"], summary["errors"], summary["deterministic"]) == (4, 0, "4 of 4")
    assert [(talk["topic"], talk["seed"]) for talk in report["talks"]] == [
        ("cat", 1),
        ("cat", 2),
        ("dog", 1),
        ("dog", 2),
    ]
    assert all(talk["metrics"]["slides"] == test_seeds.NUM_SLIDES for talk in report["talks"])
    assert json.loads(json.dumps(report)) == report


def test_a_talk_that_comes_out_differently_is_an_error(monkeypatch):
    decks = iter([_deck(TITLE), _deck(TITLE, TITLE)])
    monkeypatch.setattr(benchmark, "generate_deck", lambda *args, **kwargs: next(decks))

    talk = benchmark.check_talk("cat", 1, slides=1)

    assert talk.deterministic is False
    (error,) = talk.errors
    assert error.check == "determinism"
    assert "2 slides instead of 1" in error.message


def test_a_difference_says_what_differs(monkeypatch):
    noted = DeckSlide(type="title", layout="classic/title", elements=TITLE.elements, notes="made at 0x1")
    decks = iter([_deck(TITLE, TITLE), _deck(TITLE, noted)])
    monkeypatch.setattr(benchmark, "generate_deck", lambda *args, **kwargs: next(decks))
    (error,) = benchmark.check_talk("cat", 1, slides=2).errors
    assert error.message.endswith("other slides came out: slide 2 (notes)")


def test_a_crash_is_what_the_check_finds(monkeypatch):
    def crash(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(benchmark, "generate_deck", crash)
    assert [finding.check for finding in benchmark.check_talk("cat", 1).errors] == ["generation"]


def test_the_command_writes_a_report(fake_schema, tmp_path, capsys):
    report = tmp_path / "report.json"
    arguments = ["--topics", "cat", "--schema", "fake", "--slides", str(test_seeds.NUM_SLIDES), "--report", str(report)]

    assert benchmark.main(arguments) == 0

    assert "1 talk: 0 errors" in capsys.readouterr().out
    assert json.loads(report.read_text(encoding="utf-8"))["summary"]["talks"] == 1


def test_errors_fail_the_command(fake_schema, tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "check_deck", lambda deck, slides: [Finding("leftovers", "error", "{oops}", 1)])
    arguments = ["--topics", "cat", "--schema", "fake", "--no_determinism", "--report", str(tmp_path / "report.json")]
    assert benchmark.main(arguments) == 1


@pytest.mark.parametrize("arguments", [["--seeds", "one"], ["--schema", "no such schema"], ["--quick", "--all"]])
def test_wrong_arguments_are_refused(arguments):
    with pytest.raises(SystemExit) as exit_:
        benchmark.main(arguments)
    assert exit_.value.code == 2


def test_the_talkgenerator_command_has_a_check_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["talkgenerator", "check", "--help"])
    with pytest.raises(SystemExit) as exit_:
        run.main_cli()
    assert exit_.value.code == 0
    assert "talkgenerator check" in capsys.readouterr().out
