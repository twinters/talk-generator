"""Offline tests of milestone 6's slide types (docs/v5-plan.md, section 8): big numbers and KPI tiles, quizzes, a
social media post and a news headline, an agenda, a section's divider and "Questions?". They're texts (and a photo)
on shapes that the layouts draw, in every theme and in the classic template's look, with some texts appearing on a
click."""

import pytest
from lxml import etree
from pptx.oxml.ns import qn

from talkgenerator.checks.deck import check_completeness, check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import engine, themes
from talkgenerator.models import classic
from talkgenerator.models.deck import Deck, ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import length_limit, realize
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import conceptnet, slide_texts
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)

FAMILIES = list(themes.FAMILIES)
NEW_KINDS = ("big_number", "kpi", "quiz", "social_post", "news_headline", "agenda", "section", "questions")
DIAGRAMS = ("timeline", "pyramid", "funnel", "cycle", "org_chart", "iceberg")
EVERY_KIND = NEW_KINDS + DIAGRAMS
ENGLISH = languages.ENGLISH


def every_new_type(image):
    """One slide of every one of milestone 6's types, with what every one of their layouts takes (short numbers, four
    figures and four options, a title, a photo), each credited."""
    made = [
        slides.BigNumberSlide("The cat economy", "97%", "of cats have never paid rent", "Source: my neighbour"),
        slides.KpiSlide("Quarterly results", "1,204", "Mice caught", "+3%", "Purr growth", "-12", "Laps", "0", "Naps"),
        slides.QuizSlide("Which came first?", "The chicken", "The egg", "The rooster", "Breakfast", "D", "Obviously"),
        slides.SocialPostSlide(None, "Prof. Whiskers McPaw", "whiskers", "No regrets. #science", image, 12482, 873),
        slides.NewsHeadlineSlide("The Daily Purr", "Cat elected mayor", "Opponents demand a recount", image),
        slides.AgendaSlide("Today's menu", "Why cats", "How cats", "When cats", "Questions"),
        slides.SectionSlide("The dark years", "In which the cat finds the laser pointer"),
        slides.QuestionsSlide("Questions?", "Answers not guaranteed"),
        slides.TimelineSlide(
            "A history of cats", "3000 BC", "Cats invent Egypt", "1888", "Cats take a photo", "Today", "This talk"
        ),
        slides.PyramidSlide("Maslow for cats", "Enlightenment", "Boxes", "Naps", "Food"),
        slides.FunnelSlide("The cat funnel", "Visitors", "Petters", "Feeders", "Servants"),
        slides.CycleSlide("The cat cycle", "Sleep", "Eat", "Judge", "Repeat"),
        slides.OrgChartSlide("Who's in charge", "The cat", "Head of naps", "VP of boxes", "Chief mouser"),
        slides.IcebergSlide("The cat iceberg", "Cute photos", "Years of hairballs", "A secret empire"),
    ]
    for slide in made:
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    return made


def runs_of_new_types(image, length=3):
    """Runs of slides of every new type, each run of one type, as the design tests want them."""
    return [
        slide for index in range(len(EVERY_KIND)) for slide in (every_new_type(image)[index] for _ in range(length))
    ]


def _deck(made, theme=None, seed=1):
    slide_deck = SlideDeck(len(made), title="Cats", topics=["cats"], seed=seed)
    for index, slide in enumerate(made):
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    return slide_deck.to_deck()


def _theme(family="clean keynote", seed=1):
    return themes.pick(family, random_util.Rng(seed))


def _longest(text_field, word="Expectation"):
    """A text of the field as long as a slide takes it (its length limit), of words: or one of its options."""
    if text_field.options:
        return text_field.options[0]
    limit = length_limit(text_field)
    return " ".join([word] * (limit // len(word) + 1))[:limit].strip()


def _built(kind, texts, images=None, seed=1):
    with random_util.use(random_util.Rng(seed)):
        return KINDS[kind].build(texts, images or {}, ENGLISH)


def _longest_texts(kind):
    texts = {text.name: _longest(text) for text in KINDS[kind].texts}
    if kind == "agenda":  # (five items, each as long as an item may be)
        texts["items"] = " | ".join(["Expectation " * 4] * 5)
    if kind in ("big_number", "kpi"):  # numbers have no spaces
        texts.update({name: "1,000,000,000" for name in texts if name == "number" or name.startswith("number_")})
    return texts


# EVERY TYPE, IN EVERY THEME


@pytest.mark.parametrize("family", FAMILIES)
def test_the_longest_texts_fit_and_read_in_every_theme(images, family):
    longest = [_built(kind, _longest_texts(kind), {"photo": _image("wide")}) for kind in EVERY_KIND]
    shortest = [
        slides.BigNumberSlide(None, "7", "naps"),
        slides.KpiSlide(None, "1", "A", "2", "B", "3", "C"),
        slides.QuizSlide("Why?", "A", "B", "C", None, "a"),
        slides.SocialPostSlide(None, "Ann", "a", "Hi", None),
        slides.NewsHeadlineSlide("A", "B", None, _image("tall")),
        slides.AgendaSlide(None, "One", "Two", "Three"),
        slides.SectionSlide("Then"),
        slides.QuestionsSlide("?"),
        slides.TimelineSlide(None, "1", "A", "2", "B", "3", "C"),
        slides.PyramidSlide(None, "A", "B", "C"),
        slides.FunnelSlide(None, "A", "B", "C"),
        slides.CycleSlide(None, "A", "B", "C"),
        slides.OrgChartSlide(None, "A", "B", "C"),
        slides.IcebergSlide(None, "A", "B", "C"),
    ]
    for seed in range(3):
        deck = _deck(longest + shortest, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)
        assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == []


def test_every_new_layout_comes_up_and_needs_what_it_says(images):
    seen = set()
    for seed in range(12):
        seen |= {slide.layout for slide in _deck(runs_of_new_types(_image("wide")), _theme(seed=seed), seed).slides}
    new_layouts = {layout.name for kind in EVERY_KIND for layout in engine._LAYOUTS[kind]}
    assert new_layouts <= seen

    def fitting(slide):
        return engine.layouts_for(slide.to_deck_slide())

    assert fitting(slides.BigNumberSlide(None, "3.2 million", "hairballs")) == ["v5/big-number"]
    assert fitting(slides.BigNumberSlide(None, "1 in 4", "cats")) == ["v5/big-number", "v5/big-number-panel"]
    assert fitting(slides.QuizSlide("Why?", "A", "B", "C", None, "A")) == ["v5/quiz-list"]
    assert fitting(slides.KpiSlide("KPIs", "1", "A", "2", "B", "3", "C")) == ["v5/kpi-rows", "v5/kpi-tiles"]
    assert "v5/kpi-grid" not in fitting(slides.KpiSlide("K", "1", "A", "2", "B", "3", "C", "1,000,000,000", "D"))
    assert fitting(slides.SocialPostSlide(None, "Ann", "ann", "Hi", None)) == ["v5/post"]
    assert fitting(slides.AgendaSlide(None, "One", "Two", "Three")) == ["v5/agenda", "v5/agenda-steps"]


def test_texts_on_shapes_read_on_them(images):
    deck = _deck(every_new_type(_image("wide")), _theme("neon"))
    quiz = next(slide for slide in deck.slides if slide.type == "quiz")
    stamp = next(element for element in quiz.elements if element.role == "stamp")
    answer = quiz.element("answer")
    assert isinstance(stamp, ShapeElement) and isinstance(answer, TextElement)
    assert answer.text == "D" and answer.style.color != stamp.color
    # the right option's band: as see-through as it takes for the theme's text to read on it
    band = next(element for element in quiz.elements if element.role == "right answer")
    assert band.appears_on_click == 1 == stamp.appears_on_click == answer.appears_on_click


# CLICKS


def test_a_quizs_answer_and_a_kpis_punchline_appear_on_a_click():
    quiz = slides.QuizSlide("Why?", "A thing", "Another", "A third", None, "b", "Because").to_deck_slide()
    clicks = {element.role: element.appears_on_click for element in quiz.elements}
    assert clicks["answer"] == clicks["explanation"] == 1
    assert clicks["option_2"] is None and clicks["title"] is None
    kpi = slides.KpiSlide("KPIs", "1", "A", "2", "B", "3", "C").to_deck_slide()
    assert [element.role for element in kpi.elements if element.appears_on_click] == ["number_3", "label_3"]
    four = slides.KpiSlide("KPIs", "1", "A", "2", "B", "3", "C", "4", "D").to_deck_slide()
    assert [element.role for element in four.elements if element.appears_on_click] == ["number_4", "label_4"]
    assert Deck.from_json(Deck(generator="test", slides=(quiz,)).to_json()).slides[0] == quiz


def _clicks(ppt_slide):
    """The shapes (by name) that each click of the slide shows, in order."""
    names = {str(shape.shape_id): shape.name for shape in ppt_slide.shapes}
    timing = ppt_slide.element.find(qn("p:timing"))
    if timing is None:
        return []
    namespaces = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    steps = etree.XPath(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", namespaces=namespaces)(timing)
    targets = etree.XPath(".//p:spTgt/@spid", namespaces=namespaces)
    return [sorted({names[spid] for spid in targets(step)}) for step in steps]


@pytest.mark.parametrize("theme", [None, "clean keynote"], ids=["classic", "themed"])
def test_powerpoint_shows_the_answer_on_a_click(images, theme):
    quiz = slides.QuizSlide("Which came first?", "The chicken", "The egg", "The rooster", "Breakfast", "C", "Duh")
    deck = _deck([quiz], _theme(theme) if theme else None)
    (ppt_slide,) = render_pptx(deck).slides
    (shown,) = _clicks(ppt_slide)
    assert {"answer", "explanation", "stamp", "right answer"} <= set(shown)
    assert not {"option_1", "option_3", "title"} & set(shown)
    texts = {shape.name: shape.text_frame.text for shape in ppt_slide.shapes if shape.has_text_frame}
    assert texts["answer"] == "C" and texts["option_3"] == "The rooster" and texts["letter_3"] == "C"


@pytest.mark.parametrize(
    ("slide", "on_the_click"),
    [
        (slides.TimelineSlide("T", "1", "A", "2", "B", "3", "C"), {"date_3", "event_3", "dot_3"}),
        (slides.PyramidSlide("P", "Top", "Middle", "Base"), {"level_1", "level 1 band"}),
        (slides.FunnelSlide("F", "Wide", "Middle", "Narrow"), {"stage_3", "stage 3 band"}),
        (slides.OrgChartSlide("O", "Boss", "One", "Two"), {"boss", "boss box"}),
        (slides.IcebergSlide("I", "Tip", "Under", "Deeper"), {"hidden_1", "hidden_2"}),
    ],
    ids=["timeline", "pyramid", "funnel", "org chart", "iceberg"],
)
def test_a_diagrams_punchline_appears_on_a_click(images, slide, on_the_click):
    (shown,) = _clicks(render_pptx(_deck([slide], _theme())).slides[0])
    assert set(shown) == on_the_click


def test_a_cycle_shows_everything_at_once(images):
    assert _clicks(render_pptx(_deck([slides.CycleSlide("C", "A", "B", "C")], _theme())).slides[0]) == []


def test_powerpoint_shows_the_last_figure_with_its_tile_on_a_click(images):
    deck = _deck([slides.KpiSlide("KPIs", "1", "A", "2", "B", "3", "C")], _theme())
    (shown,) = _clicks(render_pptx(deck).slides[0])
    assert {"number_3", "label_3", "figure_3"} <= set(shown) and "number_2" not in shown


# THE CLASSIC TEMPLATE


def test_a_classic_deck_draws_the_new_types_in_the_templates_look(images):
    deck = _deck(every_new_type(_image("wide")))
    assert deck.theme == "classic" and all(slide.layout == f"classic/{slide.type}" for slide in deck.slides)
    assert all(element.box is None for slide in deck.slides for element in slide.elements)  # (placed when drawn)
    presentation = render_pptx(deck)
    assert len(presentation.slides) == len(deck.slides)
    for ppt_slide in presentation.slides:
        assert ppt_slide.slide_layout.name == "Leeg"  # (the template's blank slide, under its master)
        fonts = {
            run.font.name
            for shape in ppt_slide.shapes
            if shape.has_text_frame and not shape.is_placeholder
            for paragraph in shape.text_frame.paragraphs
            for run in paragraph.runs
        }
        assert fonts <= {"Calibri", "Calibri Light"}
        sources = [shape for shape in ppt_slide.placeholders if shape.placeholder_format.idx == 10]
        assert [shape.text_frame.text for shape in sources] == ["[Image sources: Ann (via Pexels)]"]


def test_the_classic_look_passes_the_design_checks(images):
    look = themes.CLASSIC_LOOK
    for made in (
        every_new_type(_image("wide")),
        [_built(kind, _longest_texts(kind), {"photo": _image("tall")}) for kind in EVERY_KIND],
    ):
        classic_deck = _deck(made)
        placed = tuple(
            engine.lay_out_slide(slide, look, random_util.Rng(0).child("classic", slide.type))
            for slide in classic_deck.slides
        )
        deck = classic_deck.model_copy(update={"slides": placed, "style": look, "theme": "classic look"})
        assert [finding for finding in check_design(deck) if finding.check != "variety"] == []


# PREVIEWS


def test_previews_draw_the_new_types(images):
    deck = _deck(every_new_type(_image("wide")), _theme("brutalist"))
    sheet = preview.contact_sheet(deck)
    assert sheet.width > 0
    picture = preview.slide_image(deck.slides[0], deck.style, width=480)  # a big number in the theme's accent
    accent = tuple(int(deck.style.palette.accent[index : index + 2], 16) for index in (1, 3, 5))
    assert accent in {colour for _, colour in picture.getcolors(480 * 270)}


# WHAT A PLAN ASKS FOR


def _realized(kind, texts, images=None, problems=None):
    plan = SlidePlan(kind=kind, concept="cats", texts=texts, images=images or {})
    return realize(plan, Recipe(kind), {"seed": "cats", "topic": "cats"}, random_util.Rng(1), 0, problems=problems)


def test_planned_slides_come_out_as_planned():
    quiz = {"question": "Why?", "option_a": "Yes", "option_b": "No", "option_c": "Maybe", "answer": "c"}
    slide, generated = _realized("quiz", {**quiz, "answer": "C"})
    assert isinstance(slide, slides.QuizSlide) and "Maybe" in generated
    problems = []
    assert _realized("quiz", {**quiz, "answer": "D"}, problems=problems) is None  # (there's no option D)
    assert problems == ["the quiz's answer, 'D', isn't one of its options"]
    problems = []
    assert _realized("agenda", {"title": "Agenda", "items": "One | Two"}, problems=problems) is None
    assert problems == ["an agenda needs three items or more"]
    slide, _ = _realized("agenda", {"title": "Agenda", "items": f"One | {'Very ' * 20}long | Three | | Four"})
    items = [element.text for element in slide.to_deck_slide().elements if element.role.startswith("item_")]
    assert len(items) == 4 and all(len(item) <= 45 for item in items)


def test_a_quizs_options_lose_the_letters_a_model_wrote_in_front():
    texts = {"question": "Why?", "option_a": "A) Yes", "option_b": "(b) No", "option_c": "C. Apples", "answer": "A"}
    deck_slide = _built("quiz", texts).to_deck_slide()
    assert [deck_slide.element(f"option_{index}").text for index in (1, 2, 3)] == ["Yes", "No", "Apples"]
    assert deck_slide.element("letter_3").text == "C"


def test_a_post_and_a_headline_speak_the_talks_language(images):
    dutch = languages.language("nl")
    with random_util.use(random_util.Rng(2)):
        post = KINDS["social_post"].build(
            {"title": None, "author": "Anna Tomy", "handle": "anna tomy", "text": "Hallo"}, {"photo": None}, dutch
        )
        news = KINDS["news_headline"].build(
            {"outlet": "De Kat", "headline": "Kat wint", "subheadline": None}, {"photo": _image("wide")}, dutch
        )
    elements = {element.role: element for element in post.to_deck_slide().elements}
    assert elements["initials"].text == "AT" and elements["handle"].text == "@anna_tomy"
    assert elements["stats"].text.endswith("keer gedeeld") and " likes · " in elements["stats"].text
    assert news.to_deck_slide().element("kicker").text == "NIEUWSFLITS"


def test_names_and_counts_read_like_a_posts():
    assert slides.initials("Prof. Anna Tomy") == "AT" and slides.initials("Cher") == "C" and slides.initials("") is None
    assert slides.handle("@sock lover") == "@sock_lover" and slides.handle("  ") is None
    assert [slides.count(number) for number in (7, 999, 12482, 3_400_000)] == ["7", "999", "12K", "3M"]


def test_sections_are_numbered_in_the_order_they_come(images):
    made = [
        slides.TitleSlide("Cats", None),
        slides.SectionSlide("One"),
        slides.QuestionsSlide("?"),
        slides.SectionSlide("Two"),
        slides.SectionSlide("Three", kicker="Finally"),
    ]
    deck = _deck(made)
    assert [slide.element("kicker").text for slide in deck.slides if slide.type == "section"] == ["02", "03", "Finally"]


# THE CLASSIC GENERATORS


@pytest.fixture
def related(monkeypatch):
    """Fake ConceptNet: the words related to a cat."""
    words = {"cat": [(1.0, "dog"), (0.9, "mouse"), (0.8, "cat food"), (0.7, "yarn"), (0.6, "milk"), (0.5, "whiskers")]}
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: words.get(word, []))
    return words


def _photo(context):
    return _image("wide")


CLASSIC = {
    "big_number": (slide_texts.generate_big_number, slides.BigNumberSlide),
    "kpi": (slide_texts.generate_kpi, slides.KpiSlide),
    "quiz": (slide_texts.generate_quiz, slides.QuizSlide),
    "social_post": (slide_texts.social_post(_photo), slides.SocialPostSlide),
    "news_headline": (slide_texts.news_headline(_photo), slides.NewsHeadlineSlide),
    "agenda": (slide_texts.generate_agenda, slides.AgendaSlide),
    "section": (slide_texts.generate_section, slides.SectionSlide),
    "questions": (slide_texts.generate_questions, slides.QuestionsSlide),
    "timeline": (slide_texts.generate_timeline, slides.TimelineSlide),
    "pyramid": (slide_texts.generate_pyramid, slides.PyramidSlide),
    "funnel": (slide_texts.generate_funnel, slides.FunnelSlide),
    "cycle": (slide_texts.generate_cycle, slides.CycleSlide),
    "org_chart": (slide_texts.generate_org_chart, slides.OrgChartSlide),
    "iceberg": (slide_texts.generate_iceberg, slides.IcebergSlide),
}


@pytest.mark.parametrize("kind", EVERY_KIND)
def test_the_classic_generators_make_complete_slides(images, related, kind):
    content, slide_class = CLASSIC[kind]
    generator = SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(content, slide_class), retries=1, name=kind
    )
    for seed in range(8):
        with random_util.use(random_util.Rng(seed)):
            result = generator.generate({"seed": "cat", "topic": "cats"}, set())
        assert result is not None, (kind, seed)
        slide, generated = result
        assert isinstance(slide, slide_class) and slide.missing_content() == []
        deck = _deck([slide], _theme(seed=seed), seed)
        assert [finding for finding in check_deck(deck) if finding.severity == "error"] == [], (kind, seed)


def test_a_classic_quiz_or_agenda_needs_related_words(related):
    with random_util.use(random_util.Rng(1)):
        assert slide_texts.generate_quiz({"seed": "petrichor"}) is None
        assert slide_texts.generate_kpi({"seed": "cat"}) is not None


def test_the_classic_templates_leave_nothing_behind(related):
    for seed in range(40):
        with random_util.use(random_util.Rng(seed)):
            made = [content({"seed": "cat", "topic": "cats"}) for content, _ in CLASSIC.values()]
        texts = [part for parts in made if parts for part in parts if isinstance(part, str)]
        deck = Deck(generator="test", slides=(slides.QuestionsSlide(" ".join(texts)).to_deck_slide(),))
        assert check_leftovers(deck) == []


def test_the_classic_generators_leave_sensitive_words_out(monkeypatch, related):
    related["islam"] = [(1.0, "jihad"), (0.9, "allah"), (0.8, "prayer"), (0.7, "mosque"), (0.6, "ramadan")]
    related["cat"] = [*related["cat"], (0.4, "death star"), (0.3, "god")]
    assert slide_texts.related_words("cat") == ["Dog", "Mouse", "Yarn", "Milk", "Whiskers"]  # (no "cat food" either)
    with random_util.use(random_util.Rng(1)):
        assert all(content({"seed": "islam", "topic": "cats"}) is None for content, _ in CLASSIC.values())
    assert slide_texts.sensitive("The Islam cycle") and not slide_texts.sensitive("Godzilla")


def test_a_classic_slides_texts_come_from_templates_of_their_own(related):
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            title, *moments = slide_texts.generate_timeline({"seed": "cat", "topic": "cats"})
        events = moments[1::2][:-1]  # (the last one is the punchline)
        banned = [event for event in events if event.endswith(" is banned")]
        assert len(banned) <= 1 and len(set(events)) == len(events), events


# THE FORMATS


@pytest.mark.parametrize("format_name", ["default", "ted"])
def test_every_format_has_the_new_types_once_at_most(format_name):
    schema = get_schema(format_name)
    kinds = {generator.llm.kind: generator for generator in schema.slide_generators if generator.llm is not None}
    assert set(EVERY_KIND) <= set(kinds)
    caps = schema._max_allowed_tags
    once = ("big_number", "kpi", "quiz", "social_post", "news", "agenda", "questions", *DIAGRAMS)
    assert all(caps[tag] == 1 for tag in once)
    assert caps["section"] == 0.1  # (none in a talk of fewer than ten slides)
    assert caps["diagram"] == 0.2  # (two in a talk of ten slides, Venn diagrams and matrices included)
    assert kinds["agenda"].get_weight_for(1, 10) > 0 == kinds["agenda"].get_weight_for(5, 10)
    assert kinds["questions"].get_weight_for(9, 10) > 0 == kinds["questions"].get_weight_for(5, 10)
    assert kinds["section"].get_weight_for(5, 10) > 0 == kinds["section"].get_weight_for(1, 10)
    choices = external.recipes_of(schema)
    assert {external.default_recipe(choices, kind).recipe.kind for kind in EVERY_KIND} == set(EVERY_KIND)


def test_the_ted_formats_mockups_get_copyright_free_photos():
    from talkgenerator.schema import content_generators as cg

    ted = {generator.name: generator for generator in get_schema("ted").slide_generators}
    assert ted["Social Media Post (CRF)"].llm.images == (cg.copyright_free_generator,)
    assert ted["News Headline (CRF)"].llm.images == (cg.copyright_free_generator,)


def test_the_new_types_are_drawn_types():
    assert classic.DRAWN_TYPES == set(EVERY_KIND)
    for kind in EVERY_KIND:
        slide = _built(kind, _longest_texts(kind), {"photo": ImageData("https://example.com/wide.jpg")})
        assert slide.type_name in classic.DRAWN_TYPES
