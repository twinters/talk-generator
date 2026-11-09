"""Offline tests of the automated checks: findings on hand-made decks, and benchmark runs with fake sources."""

import itertools
import json
import sys
from datetime import timedelta

import pytest

from talkgenerator import generator, run, titles
from talkgenerator.checks import benchmark
from talkgenerator.checks import deck as deck_checks
from talkgenerator.checks.deck import (
    Finding,
    check_completeness,
    check_deck,
    check_images,
    check_language,
    check_leftovers,
    check_title,
    deck_metrics,
)
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
    TopicOrTitle,
)
from talkgenerator.plan import prompt
from talkgenerator.slide import slides
from talkgenerator.util import http_util
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


def _talk_in(language, *texts, by="Door"):
    """A deck in the language, with a slide for every text."""
    title = _slide("title", _text("title", texts[0]), _text("subtitle", f"{by} Ann Example"))
    return Deck(
        generator="test",
        language=language,
        slides=(title, *(_slide("full_image", _text("title", text)) for text in texts[1:])),
    )


def test_a_dutch_talk_in_dutch_passes_the_language_check():
    deck = _talk_in(
        "nl",
        "Het geheime leven van katten",
        "Waarom de kat altijd wint",
        "Een kat op de bank is een koning",
        "Wat we hebben geleerd",
    )
    assert check_language(deck) == []


def test_a_dutch_talk_in_english_doesnt():
    deck = _talk_in(
        "nl",
        "The secret life of cats",
        "Why the cat always wins",
        "A cat on the couch is a king",
        "What we have learned from them",
    )
    findings = check_language(deck)
    assert findings[0] == Finding("language", "error", "the talk reads as English, not Dutch")
    assert {finding.slide for finding in findings[1:]} <= {2, 3, 4, 5}


def test_one_english_slide_in_a_dutch_talk_is_a_warning():
    deck = _talk_in("nl", "Het geheime leven van katten", "Waarom de kat altijd wint", "What we have learned from them")
    assert check_language(deck) == [Finding("language", "warning", "reads as English, not Dutch", 3)]


def test_a_swedish_talk_in_swedish_passes_the_language_check():
    deck = _talk_in(
        "sv",
        "Kattens hemliga liv",
        "Varför katten alltid vinner",
        "En katt i soffan är en kung",
        "Det här har vi lärt oss",
        by="Av",
    )
    assert check_language(deck) == []


def test_a_swedish_talk_in_english_doesnt():
    deck = _talk_in(
        "sv",
        "The secret life of cats",
        "Why the cat always wins",
        "A cat on the couch is a king",
        "What we have learned from them",
        by="Av",
    )
    findings = check_language(deck)
    assert findings[0] == Finding("language", "error", "the talk reads as English, not Swedish")
    assert {finding.slide for finding in findings[1:]} == {2, 3, 4}  # (the title slide's "Av" is Swedish)
    one = _talk_in(
        "sv", "Det hemliga livet för katter", "Varför katten alltid vinner", "What we have learned from them", by="Av"
    )
    assert check_language(one) == [Finding("language", "warning", "reads as English, not Swedish", 3)]


def test_swedish_words_that_look_like_english_ones_dont_make_a_slide_read_as_english():
    # (all, into, just, ice: English stopwords, and words of Swedish that its stopwords leave out)
    deck = _talk_in("sv", "Kattens hemliga liv", "All glass in", "Just is", by="Av")
    assert check_language(deck) == []
    english = _talk_in("sv", "Kattens hemliga liv", "All of the ice", by="Av")
    assert check_language(english) == [Finding("language", "warning", "reads as English, not Swedish", 2)]


def test_english_talks_have_no_language_to_check():
    assert check_language(_talk_in("en", "Het geheime leven van katten", "Waarom de kat wint")) == []


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
        # (a free model's conclusion called back to an earlier slide by its key in the model's answer)
        ("Huddling scales trust (from slide_03)", "a slide's key in the language model's answer"),
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


@pytest.mark.parametrize(
    "title, words",
    [
        # (Claude Haiku took the request's "Title: come up with one" for the title, 2026-11-08)
        ("Come Up With One: Retrocausal Roasting in Arabica Beans", "Come Up With One"),
        ("Fernix One: Come Up With One. Master Houseplants in Five Steps", "Come Up With One"),
        ("A Title of Your Own for the Talk", "Title of Your Own"),
        ("Penguins, as the User Typed Them", "the User Typed"),
    ],
)
def test_a_title_with_its_request_s_own_words_is_a_warning(title, words):
    deck = Deck(generator="test", title=title, topics=("coffee",), slides=(TITLE,))
    (finding,) = check_title(deck)
    assert (finding.check, finding.severity, finding.slide) == ("title", "warning", 1)
    assert finding.message == f"its title has the request's own words: {words!r} in {title!r}"
    assert finding in check_deck(deck)


@pytest.mark.parametrize(
    "title", ["Why I Joined a Penguin Cult", "Come Up With Ones and Zeros", "The Talk's Titles Are Lies", "Cats"]
)
def test_a_title_of_its_own_is_no_finding(title):
    assert check_title(Deck(generator="test", title=title, topics=("cats",), slides=(TITLE,))) == []


def test_a_title_may_have_the_request_s_words_that_were_typed_for_it():
    typed = TopicOrTitle(text="How to come up with one good idea", read_as="title")
    deck = Deck(generator="test", title="How to Come Up With One Good Idea", topic_or_title=typed, slides=(TITLE,))
    assert check_title(deck) == []


def test_the_check_knows_what_the_request_says_of_a_title():
    # (so that a title that echoes the request's words about it gets a warning, however it's asked for)
    asked = [
        prompt.spine()["title"],
        prompt.spine(titled=True)["title"],
        *titles.TitleRequest("cats").fields().values(),
        *titles.TitleRequest("cats", candidates=("Cats, Explained",)).fields().values(),
        *titles.TitleRequest("Why I Joined a Penguin Cult", keep=True).fields().values(),
        *titles.TitleRequest("Cats are liquid", exact=True).fields().values(),
    ]
    assert [description for description in asked if not deck_checks._REQUEST_WORDS.search(description)] == []


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


def test_a_closing_slides_callback_may_show_an_earlier_picture_again():
    """A closing slide that calls back shows an earlier slide's picture again on purpose (docs/v5-plan.md, D65), as a
    free model's pitch did ("Remember the WaddleDrone?"): no finding. Any other slide that shows it again is one."""
    findings = check_images(
        _deck(
            _slide("image", _image("content")),
            _slide("questions", _text("title", "Questions?"), _text("subtitle", "Remember this?"), _image("photo")),
            _slide("image", _image("content")),
        )
    )
    assert [(finding.slide, finding.message) for finding in findings] == [(3, "the same image as slide 1")]


def test_the_required_roles_are_what_the_slide_classes_require():
    types = {
        slides.TitleSlide: "title",
        slides.LarqeQuoteSlide: "large_quote",
        slides.ImageSlide: "image",
        slides.FullImageSlide: "full_image",
        slides.TwoColumnImageSlide: "two_column_image",
        slides.ThreeColumnImageSlide: "three_column_image",
        slides.ChartSlide: "chart",
        slides.DiagramSlide: "diagram",
        slides.BigNumberSlide: "big_number",
        slides.KpiSlide: "kpi",
        slides.QuizSlide: "quiz",
        slides.SocialPostSlide: "social_post",
        slides.NewsHeadlineSlide: "news_headline",
        slides.AgendaSlide: "agenda",
        slides.SectionSlide: "section",
        slides.QuestionsSlide: "questions",
        slides.TimelineSlide: "timeline",
        slides.PyramidSlide: "pyramid",
        slides.FunnelSlide: "funnel",
        slides.CycleSlide: "cycle",
        slides.OrgChartSlide: "org_chart",
        slides.IcebergSlide: "iceberg",
        slides.MemeSlide: "meme",
        slides.FunFactSlide: "fun_fact",
        slides.AcronymSlide: "acronym",
        slides.DareSlide: "dare",
        slides.FlowchartSlide: "flowchart",
        slides.TierListSlide: "tier_list",
        slides.ProcessSlide: "process",
        slides.ReferencesSlide: "references",
        slides.WallOfTextSlide: "wall_of_text",
        slides.AlignmentChartSlide: "alignment_chart",
        slides.RedFlagsSlide: "red_flags",
        slides.ReviewsSlide: "reviews",
        slides.ErrorMessageSlide: "error_message",
        slides.ProblemSlide: "problem",
    }
    assert set(types.values()) == set(classic.REQUIRED_ROLES) == set(classic.CLASSIC_ROLES)
    for slide_class, slide_type in types.items():
        roles = classic.CLASSIC_ROLES[slide_type]
        # A chart's type and data make one chart element
        required = {roles.get(argument, "chart") for argument in slide_class.required_arguments}
        assert required == set(classic.REQUIRED_ROLES[slide_type]), slide_type


def test_the_metrics_say_whether_images_match_their_queries_and_titles_repeat():
    def found(query, description):
        image = ImageAsset(url=f"https://example.com/{query}.jpg", query=query, description=description)
        return ImageElement(role="image", image=image)

    deck = _deck(
        TITLE,
        _slide("image", _text("title", "Look at this"), found("cats on a roof", "A cat sitting on a red roof")),
        _slide("image", _text("title", "look at this"), found("a cat in sunglasses", "Dog wearing a hat")),
        _slide("image", _text("title", "Then"), found("old typewriter", "")),  # nothing to compare with
    )
    metrics = deck_metrics(deck)
    assert metrics["images_with_query_and_description"] == 2
    assert metrics["images_matching_their_query"] == 1
    assert metrics["repeated_titles"] == 1


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


def test_the_second_run_gets_the_answers_the_first_run_got(monkeypatch):
    """An answer of the on-disk cache can expire between a talk's two runs (Pixabay's do, after a day) and come back
    different (Pixabay's image links change from one day to the next): the talk came out differently, but no slide
    had."""
    monkeypatch.setitem(http_util.CACHE_EXPIRY, "words.example/api", timedelta(days=1))
    words = (f"word {number}" for number in itertools.count())

    class Answer:
        ok = True
        status_code = 200

        def __init__(self):
            self.word = next(words)

        def json(self):
            return {"word": self.word}

    class Source:
        def request(self, method, url, timeout, **kwargs):
            return Answer()

    def search():
        return http_util.get_json("https://words.example/api", params={"q": "cat"})["word"]

    monkeypatch.setattr(http_util, "get_session", Source)
    monkeypatch.setattr(
        benchmark, "generate_deck", lambda *args, **kwargs: _deck(_slide("title", _text("title", search())))
    )

    assert benchmark.check_talk("cat", 1, slides=1).deterministic
    assert search() == "word 1"  # (the check asked once; now, outside it, it's asked again)


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


def test_the_command_can_save_every_deck(fake_schema, tmp_path, capsys):
    arguments = ["--topics", "time travel", "--schema", "fake", "--slides", str(test_seeds.NUM_SLIDES)]
    arguments += ["--no_determinism", "--report", str(tmp_path / "report.json"), "--decks", str(tmp_path / "decks")]
    assert benchmark.main(arguments) == 0
    (saved,) = (tmp_path / "decks").iterdir()
    assert saved.name == "time-travel-1.deck.json"
    assert len(Deck.model_validate_json(saved.read_text(encoding="utf-8")).slides) == test_seeds.NUM_SLIDES


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
