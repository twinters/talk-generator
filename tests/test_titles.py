"""Offline tests of what's typed for a talk, which can be its topic or its title (talkgenerator.titles): talkgenerator's
guess, the topics it gives, a typed title that the language model fixes (or rewrites), the classic titles a model may
pick, and talks on a topic_or_title, classic and written by the fake models of test_llm_talks and test_streaming,
made at once and streamed.
"""

import json

import pytest

from talkgenerator import generator, llm, titles
from talkgenerator.models.deck import TopicOrTitle
from talkgenerator.models.events import TalkStarted
from talkgenerator.plan.prompt import SPINE
from talkgenerator.sources import wikihow, word_frequency
from talkgenerator.util import image_util, random_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _jpeg, fake_schema
from tests.test_streaming import AlphabeticalModel, SlowModel, _flat


@pytest.fixture(autouse=True)
def images(monkeypatch):
    """Every image at example.com exists (downloaded or probed); local files load as usual."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: jpeg if url.startswith("https://example.com/") else load(url)
    )
    monkeypatch.setattr(
        image_util, "probe", lambda url: url.startswith("https://example.com/") or load(url) is not None
    )


# GUESSING, WITHOUT A LANGUAGE MODEL

TOPICS = [
    "penguins",
    "artificial intelligence",
    "medieval cheese making",
    "cats, dogs, birds, fish",
    "Penguin uprising",
]
TITLES = [
    "Why I Joined a Penguin Cult",
    "why i joind a pengiun cult",  # (misspelled)
    "How to train your dragon",
    "The French Revolution",  # (a topic too, but it starts like a title)
    "My dog",
    "Are penguins real?",
    "Penguins!",
    '"Ten things you never knew about cheese"',
    "Cats are liquid",  # (a claim)
    "Breakfast is overrated",
]


@pytest.mark.parametrize("typed", TOPICS)
def test_a_few_words_are_guessed_to_be_a_topic(typed):
    assert titles.guess(typed) == titles.TOPIC


@pytest.mark.parametrize("typed", TITLES)
def test_four_words_a_title_s_start_or_end_or_a_claim_are_guessed_to_be_a_title(typed):
    assert titles.guess(typed) == titles.TITLE


def test_titles_start_like_titles_and_claims_read_like_claims_in_the_talk_s_language_too():
    assert titles.guess("Het weer") == titles.TOPIC
    assert titles.guess("Het weer", "nl") == titles.TITLE
    assert titles.guess("Waarom katten", "nl") == titles.TITLE
    assert titles.guess("Why cats", "nl") == titles.TITLE  # (English goes for every language)
    assert titles.guess("Katten zijn vloeibaar") == titles.TOPIC
    assert titles.guess("Katten zijn vloeibaar", "nl") == titles.TITLE


def test_the_topics_come_from_a_title_s_rarest_word_and_otherwise_from_what_was_typed():
    assert titles.topics_from("Why I Joined a Penguin Cult") == ["Penguin"]
    assert titles.topics_from('  "My trip to Zorblaxia"  ') == ["Zorblaxia"]  # (unknown: the rarest)
    assert titles.topics_from("penguins") == ["penguins"]
    assert titles.topics_from("cats, dogs") == ["cats", "dogs"]
    assert titles.topics_from("medieval  cheese making") == ["medieval cheese making"]


def test_a_misspelled_word_doesnt_become_the_topic():
    # A misspelling is a word no language knows (or hardly), so the rarest: it's taken as the word it's likely to be
    assert titles.topics_from("why i joind a pengiun cult") == ["penguin"]
    assert titles.topics_from("waht my cat taught me about taxes") == ["taxes"]  # (not "waht")
    assert titles.topics_from("how too become a profesional napper") == ["napper"]  # (a rare word, but a word)
    assert word_frequency.get_rarest_word("why i joind a pengiun cult") == "joind"  # (as before, without the fix)


def test_a_misspelled_topic_is_fixed_too():
    assert titles.topics_from("pengiuns") == ["penguins"]
    assert titles.topics_from("Quantim physics, blockchian") == ["Quantum physics", "blockchain"]
    assert titles.topics_from("axolotls") == ["axolotls"]  # (rare, but no misspelling)
    assert word_frequency.fix_spelling("Waht a PROFESIONAL airplain") == "What a PROFESSIONAL airplane"
    assert word_frequency.fix_spelling("Zorblaxia") == "Zorblaxia"  # (made up: nothing like it)
    assert word_frequency.fix_spelling("un profesional", "es") == "un profesional"  # (Spanish)


def test_the_rarest_word_of_a_title_in_another_language_keeps_its_accents():
    assert titles.topics_from("Waarom ik bij een pinguïnsekte ging", "nl") == ["pinguïnsekte"]
    assert titles.topics_from("Why I Joined a Penguin Cult", "nl") == ["Penguin"]  # (its words may be English)


# A TITLE THAT WAS TYPED


@pytest.mark.parametrize(
    ("typed", "written"),
    [
        ("why i joind a pengiun cult", "Why I Joined a Penguin Cult"),
        ("How to trane you're dragon", "How to Train Your Dragon"),
        ("Why I joined penguin cult", "Why I Joined a Penguin Cult"),
        ("Cats are liquid", "Cats Are Liquid"),
        ("waarom ik bij een pinguinsekte ging", "Waarom ik bij een pinguïnsekte ging"),
    ],
)
def test_a_typed_title_with_its_slips_fixed_is_still_that_title(typed, written):
    assert titles.recognisable(typed, written)


@pytest.mark.parametrize(
    "written",
    [
        "Why I Joined a Penguin Cult (and You Should Too)",  # extended
        "My Life Among the Penguins: A Cult Story",  # rewritten
        "Waarom ik lid werd van een pinguïnsekte",  # translated
        "Penguin Cult",  # cut
        "Typed: Why I Joined Penguin Cult",  # with a word put before it
        "",
    ],
)
def test_a_typed_title_rewritten_isnt(written):
    assert not titles.recognisable("Why I Joined a Penguin Cult", written)


def test_a_typed_title_can_be_part_of_a_longer_one():
    longer = "Cats Are Liquid: A Medieval Scientific Breakthrough"
    assert titles.part_of("cats are liquid", longer) == "Cats Are Liquid"
    assert titles.part_of("cats r liquid", "Why Cats Are Liquid") is None
    assert titles.part_of("waht my cat taught me", "What My Cat Taught Me, Twice") == "What My Cat Taught Me"


def _settled(spine, typed="why i joind a pengiun cult", written=True):
    titling = titles.Titling.of(typed, written=written)
    return titling.settle(spine, lambda: "A classic title")


def test_a_clear_title_stays_with_the_slips_the_model_fixed():
    title, reading = _settled({"title": "Why I Joined a Penguin Cult"})
    assert title == "Why I Joined a Penguin Cult"
    assert reading == TopicOrTitle(text="why i joind a pengiun cult", read_as="title")
    title, _ = _settled({"title": "Cheese Is the Future of Money?"}, "is cheese the future of money?")
    assert title == "Cheese Is the Future of Money?"


def test_a_clear_title_stays_whatever_title_the_model_writes():
    # (The free models took some for topics, and gave them a classic title)
    title, reading = _settled({"title": "Never, Ever Clean A Toaster"}, "10 reasons your toaster hates you")
    assert (title, reading.read_as) == ("10 reasons your toaster hates you", "title")
    # (As typed, with the slips fixed that talkgenerator can fix itself: misspellings, an all lower-case start)
    title, _ = _settled({"title": "My Life Among the Penguins: A Cult Story"})
    assert title == "Why I joined a penguin cult"
    # (Or its part of a longer title of the model's, in the model's words)
    title, _ = _settled({"title": "Why I Joined a Penguin Cult: A Love Story"})
    assert title == "Why I Joined a Penguin Cult"


def test_a_short_input_gets_the_model_s_own_title():
    # ("The French Revolution" deserves better than itself, and a premise a funnier title that keeps its words)
    title, reading = _settled({"title": "Let Them Eat Croissants"}, "The French Revolution")
    assert (title, reading) == ("Let Them Eat Croissants", TopicOrTitle(text="The French Revolution", read_as="topic"))
    title, reading = _settled({"title": "Cats Are Liquid: The Rheology of Napping"}, "cats are liquid")
    assert (title, reading.read_as) == ("Cats Are Liquid: The Rheology of Napping", "topic")
    title, _ = _settled({"title": "The Penguin Gospel"}, typed="penguin cults")
    assert title == "The Penguin Gospel"


def test_a_model_that_only_gives_back_what_was_typed_gets_its_own_title_when_it_wrote_one():
    spine = {"own_title": "The Croissant Uprising of 1789", "title": "The French Revolution"}
    title, reading = _settled(spine, "The French Revolution")
    assert (title, reading.read_as) == ("The Croissant Uprising of 1789", "topic")
    title, _ = _settled({"title": "The French Revolution"}, "The French Revolution")  # (no other title of its own)
    assert title == "The French Revolution"
    title, _ = _settled({"own_title": "The Penguin Gospel", "title": "{seed}"}, typed="penguin cults")
    assert title == "The Penguin Gospel"


def test_a_label_the_model_copied_from_the_request_is_left_out():
    title, reading = _settled({"title": "Title: Why I Joined a Penguin Cult"})
    assert (title, reading.read_as) == ("Why I Joined a Penguin Cult", "title")
    title, _ = _settled({"title": "Topic: The Quantum Court"}, typed="quantim physics")
    assert title == "The Quantum Court"


@pytest.mark.parametrize("spine", [{}, {"title": ""}, {"title": "{seed}"}, {"title": 1}])
def test_without_a_title_from_the_model_talkgenerator_guesses(spine):
    title, reading = _settled(spine)
    assert (title, reading.read_as) == ("Why I joined a penguin cult", "title")
    title, reading = _settled(spine, typed="penguin cults")
    assert (title, reading.read_as) == ("A classic title", "topic")
    title, reading = _settled(spine, typed="cats are liquid")  # (a claim: the guess keeps it, polished)
    assert (title, reading.read_as) == ("Cats are liquid", "title")


def test_a_title_in_quote_marks_stays_word_for_word():
    # (talkgenerator.com has no other way to say it's a title; not even its slips are fixed)
    for quote in ('"{}"', "“{}”", "'{}'"):
        typed = quote.format("cats are liquid")
        assert titles.quoted(typed) and titles.guess(typed) == titles.TITLE
        assert titles.topics_from(typed) == ["liquid"]
        title, reading = _settled({"title": "Cats Are Liquid: The Rheology of Napping"}, typed)
        assert (title, reading) == ("cats are liquid", TopicOrTitle(text="cats are liquid", read_as="title"))
        title, _ = _settled({}, typed, written=False)
        assert title == "cats are liquid"
    assert not titles.quoted("cats are liquid") and not titles.quoted("'Twas the night") and not titles.quoted('""')


def test_a_title_in_quote_marks_is_asked_for_word_for_word():
    request = titles.Titling.of('"why i joind a pengiun cult"', written=True).request
    assert request is not None and request.exact and not request.candidates
    assert request.lines("penguin") == [
        "Topic: penguin",
        'Title: "why i joind a pengiun cult" (as the user typed it, in quotes: word for word)',
    ]
    assert request.fields()["title"].startswith("the title the user typed, word for word, exactly as it is")


def test_without_a_language_model_the_guess_decides_and_a_title_stays_as_typed():
    # (Whatever a spine says: there's no model, so nothing it wrote counts)
    title, reading = _settled({"title": "The Penguin Gospel"}, written=False)
    assert (title, reading.read_as) == ("Why I joined a penguin cult", "title")
    title, reading = _settled({}, typed="penguins", written=False)
    assert (title, reading.read_as) == ("A classic title", "topic")
    title, reading = _settled({}, typed="The French Revolution", written=False)  # (it starts like a title)
    assert (title, reading.read_as) == ("The French Revolution", "title")


# CLASSIC TITLES A LANGUAGE MODEL MAY PICK


def test_wikihow_s_how_tos_are_the_pages_that_teach_an_action():
    assert wikihow.action_of("How to Draw a Penguin") == "Draw a Penguin"
    assert wikihow.action_of("4 Easy Ways to Draw Cute and Realistic Cats") == "Draw Cute and Realistic Cats"
    assert wikihow.action_of("Simple Ways to Make Cheese") == "Make Cheese"
    assert wikihow.action_of("How to Take a Screenshot on a Windows PC: 8 Simple Tricks") == (
        "Take a Screenshot on a Windows PC"
    )
    assert wikihow.action_of("How to Have a Long, Passionate Kiss (And What It’s Like)") == (
        "Have a Long, Passionate Kiss"
    )
    for page in (
        "The 20 Top Games Like Club Penguin",  # (was "e 20 Top Games Like Club Penguin")
        "330 Cool & Unique Names for Penguins",
        "All There Is to Know About the Nihilist Penguin Meme",  # (was "Know About the Nihilist Penguin Meme")
        "The Best Grilled Cheese Recipes to Make at Home",
        "How Do You Store Cheese?",
        "Am I Gay Quiz",
        "Category: Cheese",
    ):
        assert wikihow.action_of(page) is None, page


def _counting(name, calls, result=None):
    def generate(context):
        calls.append(name)
        return result if result is not None else f"{name} {context['seed']} {random_util.randint(0, 99)}"

    return generate


def test_the_dice_draw_one_to_three_classic_titles():
    counts = set()
    for seed in range(40):
        calls = []
        generators = [_counting(name, calls) for name in ("first", "how-to", "again")]
        drawn = titles.candidates(generators, "penguins", random_util.Rng(seed))
        assert 1 <= len(drawn) <= 3
        assert calls == ["first", "how-to", "again"][: len(drawn)]  # (only as many as wanted are made)
        assert drawn == titles.candidates(generators, "penguins", random_util.Rng(seed))  # (the same seed: the same)
        counts.add(len(drawn))
    assert counts == {1, 2, 3}


def test_the_first_classic_title_is_the_one_a_classic_talk_gets():
    rng = random_util.Rng(7)
    first = titles.candidates([_counting("classic", [])], "penguins", rng)[0]
    with random_util.use(rng.child("title")):
        assert first == _counting("classic", [])({"seed": "penguins"})


def test_classic_titles_that_fail_repeat_or_miss_the_topic_are_left_out():
    def crash(context):
        raise RuntimeError("a source that broke")

    rng = next(random_util.Rng(seed) for seed in range(100) if _wanted(random_util.Rng(seed)) == 3)
    drawn = titles.candidates(
        [
            _counting("same", [], "How to Fly a Penguin"),
            crash,
            _counting("none", [], ""),
            _counting("off", [], "Never, Ever Be A Secret Agent"),  # (an odd wikiHow page)
            _counting("same", [], "HOW TO FLY A PENGUIN"),
            _counting("plural", [], "The Penguin Gospel"),
        ],
        "penguins",
        rng,
    )
    assert drawn == ("How to Fly a Penguin", "The Penguin Gospel")


def _wanted(rng):
    with random_util.use(rng.child("title", "candidates")):
        return random_util.randint(1, 3)


def test_the_talk_s_dice_pick_how_the_classic_titles_go():
    # (As titles to pick, as inspiration only, or not at all: the user liked the titles all three gave)
    generators = [_counting("classic", [])]
    ways = {}
    for seed in range(60):
        request = titles.Titling.of("penguins", "en", True, generators, "penguins", random_util.Rng(seed)).request
        again = titles.Titling.of("penguins", "en", True, generators, "penguins", random_util.Rng(seed)).request
        assert request == again  # (the same seed: the same way)
        way = "none" if not request.candidates else "inspiration" if request.inspiration else "options"
        ways.setdefault(way, request)
    assert set(ways) == {"options", "inspiration", "none"}
    options, inspiration, none = ways["options"], ways["inspiration"], ways["none"]
    assert options.lines("penguins")[2].startswith("Classic titles from talkgenerator, to pick from:")
    assert list(options.fields()) == ["own_title", "title"]
    assert inspiration.lines("penguins")[2].startswith(
        "Classic talkgenerator titles, for inspiration only (write your own):"
    )
    assert list(inspiration.fields()) == ["title"]
    assert len(none.lines("penguins")) == 2 and list(none.fields()) == ["title"]


def test_without_classic_titles_none_are_made(monkeypatch):
    # (Not even the wikiHow search before the request, which takes the most time)
    monkeypatch.setattr(titles, "CLASSIC_TITLE_WAYS", (("none", 1.0),))
    calls = []
    request = titles.Titling.of("penguins", "en", True, [_counting("classic", calls)], "penguins", random_util.Rng(1))
    assert request.request is not None and request.request.candidates == () and calls == []


def test_a_misspelled_short_input_tells_the_model_what_it_means():
    request = titles.Titling.of("pengiuns", written=True).request
    assert request is not None and request.meaning == "penguins"
    assert request.lines("penguins")[0] == (
        'Topic: "pengiuns" (as the user typed it, meaning "penguins": the talk\'s topic, or a premise for it)'
    )
    assert titles.Titling.of("penguins", written=True).request.meaning is None


def test_only_talks_in_english_get_classic_titles_to_weigh():
    generators = [_counting("classic", [])]
    english = titles.Titling.of("penguins", "en", True, generators, "penguins", random_util.Rng(1))
    dutch = titles.Titling.of("pinguïns", "nl", True, generators, "pinguïns", random_util.Rng(1))
    classic = titles.Titling.of("penguins", "en", False, generators, "penguins", random_util.Rng(1))
    assert english.request is not None and english.request.candidates
    assert dutch.request is not None and dutch.request.candidates == ()
    assert classic.request is None


# CLASSIC TALKS ON A TOPIC OR A TITLE


@pytest.fixture
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _classic_talk(**options):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake", slides=NUM_SLIDES, presenter="Ann Example", int_seed=1, save_ppt=False, llm="none", **options
    )
    return slide_deck.to_deck()


def test_a_classic_talk_on_a_title_keeps_it_as_typed(schema):
    deck = _classic_talk(topic_or_title="Why I joined a penguin cult")
    assert deck.title == "Why I joined a penguin cult"
    assert deck.topics == ("penguin",)
    assert deck.topic_or_title == TopicOrTitle(text="Why I joined a penguin cult", read_as="title")
    assert deck.slides[0].elements[0].text == "Why I joined a penguin cult"


def test_a_classic_talk_on_a_topic_gets_a_classic_title(schema):
    deck = _classic_talk(topic_or_title="  penguins ")
    assert deck.title == "A classic title about penguins"
    assert deck.topics == ("penguins",)
    assert deck.topic_or_title == TopicOrTitle(text="penguins", read_as="topic")
    assert deck.to_json() == _classic_talk(topic_or_title="penguins").to_json()


def test_a_topic_or_a_title_given_as_such_is_taken_as_it_is(schema):
    as_topic = _classic_talk(topic="Why I joined a penguin cult")
    assert (as_topic.topics, as_topic.title) == (
        ("Why I joined a penguin cult",),
        "A classic title about Why I joined a penguin cult",
    )
    assert as_topic.topic_or_title is None and "topic_or_title" not in as_topic.to_json()
    as_title = _classic_talk(title="penguins")
    assert (as_title.title, as_title.topics, as_title.topic_or_title) == ("penguins", ("penguins",), None)


def test_a_topic_or_title_goes_without_a_topic_and_a_title(schema):
    with pytest.raises(ValueError, match="topic_or_title"):
        _classic_talk(topic_or_title="penguins", topic="penguins")
    with pytest.raises(ValueError, match="topic_or_title"):
        _classic_talk(topic_or_title="penguins", title="Penguins")


def test_a_streamed_classic_talk_says_how_it_read_what_was_typed(schema):
    events = list(
        generator.stream_talk(
            "fake", NUM_SLIDES, topic_or_title="Why I joined a penguin cult", presenter="Ann", int_seed=1, llm="none"
        )
    )
    started, finished = events[0], events[-1]
    assert isinstance(started, TalkStarted)
    assert started.title == finished.deck.title == "Why I joined a penguin cult"
    assert started.topic_or_title == finished.deck.topic_or_title
    assert started.topic_or_title is not None and started.topic_or_title.read_as == "title"


def test_the_command_line_takes_a_topic_or_title():
    args = generator.get_argument_parser().parse_args(["--topic_or_title", "Why I Joined a Penguin Cult"])
    assert (args.topic_or_title, args.topic, args.title) == ("Why I Joined a Penguin Cult", "", None)


# TALKS A LANGUAGE MODEL WRITES

TYPED_TITLE = "why i joind a pengiun cult"
FIXED_TITLE = "Why I Joined a Penguin Cult"
POLISHED_TITLE = "Why I joined a penguin cult"  # (what talkgenerator fixes itself, when the model doesn't)


def _writes(title=None, own_title=None):
    """A change to the fake model's answer: the title it wrote, and its own (when it's asked for one)."""

    def change(answer):
        if title is not None:
            answer[SPINE]["title"] = title
        if own_title is not None and "own_title" in answer[SPINE]:
            answer[SPINE]["own_title"] = own_title

    return change


def _talk(model, int_seed=1, parallel=True, **options):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=NUM_SLIDES,
        presenter="Ann Example",
        int_seed=int_seed,
        parallel=parallel,
        save_ppt=False,
        llm=model,
        **options,
    )
    return slide_deck.to_deck(schema_name="fake")


def _lines(request):
    return request.messages[0].content.splitlines()


def _spine_schema(request):
    return request.json_schema["properties"][SPINE]["properties"]


def test_a_clear_title_is_asked_for_as_typed_with_its_slips_fixed(schema):
    model = FakeModel()
    _talk(model, topic_or_title=TYPED_TITLE)
    (request,) = model.requests
    lines = _lines(request)
    assert lines[:2] == [
        "Topic: penguin",
        f'Title: "{TYPED_TITLE}" (as the user typed it: keep its words, fixing only its spelling, grammar and capitals)',
    ]
    assert "(the typed title keeps its words)" in lines[2]
    assert not any(line.startswith("Classic") for line in lines)
    spine = _spine_schema(request)
    assert list(spine)[:3] == ["unsafe_topic", "thesis", "title"] and "own_title" not in spine
    assert spine["title"]["description"].startswith("the title the user typed, word for word")
    assert "Ann Example" not in request.system + json.dumps(request.model_dump())


def test_a_short_input_is_asked_for_a_funnier_title_with_classic_ones_to_pick(schema):
    model = FakeModel()
    _talk(model, topic_or_title="penguin cults")
    lines = _lines(model.requests[0])
    assert lines[:2] == [
        'Topic: "penguin cults" (as the user typed it: the talk\'s topic, or a premise for it)',
        "Title: come up with one, funnier and more specific than what the user typed",
    ]
    assert lines[2].startswith('Classic titles from talkgenerator, to pick from: "A classic title about penguin cults"')
    spine = _spine_schema(model.requests[0])
    assert list(spine)[:4] == ["unsafe_topic", "thesis", "own_title", "title"]
    assert "funnier and more specific than what the user typed" in spine["own_title"]["description"]


def test_a_topic_or_title_given_as_such_is_asked_for_as_before(schema):
    model = FakeModel()
    _talk(model, topic="penguins")
    lines = _lines(model.requests[0])
    assert lines[:2] == ["Topic: penguins", "Title: come up with one"]
    assert lines[2].startswith("Language: write the title, the presenter's job and every slide in English")
    spine = _spine_schema(model.requests[0])
    assert "own_title" not in spine
    assert spine["title"]["description"] == "the talk's title, in English (at most 80 characters)"


def test_a_clear_title_keeps_its_words_with_its_slips_fixed(schema):
    deck = _talk(FakeModel(change=_writes(FIXED_TITLE)), topic_or_title=TYPED_TITLE)
    assert deck.title == deck.slides[0].elements[0].text == FIXED_TITLE
    assert deck.topic_or_title == TopicOrTitle(text=TYPED_TITLE, read_as="title")
    assert deck.topics == ("penguin",)  # (a misspelling isn't the topic)
    assert all("Planned:" in slide.notes for slide in deck.slides)


def test_a_clear_title_the_model_rewrites_stays_as_typed_with_talkgenerator_s_fixes(schema):
    deck = _talk(FakeModel(change=_writes("Penguins: My Cult Years")), topic_or_title=TYPED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as) == (POLISHED_TITLE, "title")


def test_a_short_input_gets_the_model_s_title(schema):
    deck = _talk(FakeModel(change=_writes("The Penguin Gospel", "The Penguin Gospel")), topic_or_title="penguins")
    assert (deck.title, deck.topics) == ("The Penguin Gospel", ("penguins",))
    assert deck.topic_or_title == TopicOrTitle(text="penguins", read_as="topic")


def test_a_title_in_quote_marks_stays_word_for_word_in_a_talk(schema):
    deck = _talk(
        FakeModel(change=_writes("Cats Are Liquid: The Rheology of Napping")), topic_or_title='"Cats are liquid"'
    )
    assert (deck.title, deck.topic_or_title) == (
        "Cats are liquid",
        TopicOrTitle(text="Cats are liquid", read_as="title"),
    )
    assert deck.topics == ("liquid",)
    classic = _talk("none", topic_or_title="“Cats are liquid”")
    assert (classic.title, classic.topic_or_title.read_as) == ("Cats are liquid", "title")


def test_a_premise_gets_a_funnier_title_and_stays_the_talk_s_topic(schema):
    title = "Cats Are Liquid: The Rheology of Napping"
    deck = _talk(FakeModel(change=_writes(title)), topic_or_title="cats are liquid")
    assert (deck.title, deck.topic_or_title.read_as, deck.topics) == (title, "topic", ("cats are liquid",))


def test_a_model_that_writes_no_title_leaves_it_to_the_guess(schema):
    deck = _talk(FakeModel(change=_writes("")), topic_or_title=TYPED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as) == (POLISHED_TITLE, "title")
    deck = _talk(FakeModel(change=_writes("", "")), topic_or_title="penguins")
    assert (deck.title, deck.topic_or_title.read_as) == ("A classic title about penguins", "topic")


def test_a_model_that_fails_leaves_a_classic_talk_to_the_guess(schema):
    deck = _talk(FakeModel(fail=llm.RateLimited("free quota used up")), topic_or_title=TYPED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as) == (POLISHED_TITLE, "title")
    deck = _talk(FakeModel(fail=llm.RateLimited("free quota used up")), topic_or_title="penguins")
    assert deck.title == "A classic title about penguins"


class _Declining(FakeModel):
    """Writes the talk, then declines (what it wrote isn't to be used)."""

    def complete(self, request):
        return super().complete(request).model_copy(update={"finish": "refused"})


def test_a_model_that_declines_leaves_it_to_the_guess(schema):
    deck = _talk(_Declining(change=_writes("The Penguin Gospel")), topic_or_title=FIXED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as) == (FIXED_TITLE, "title")
    deck = _talk(_Declining(change=_writes("The Penguin Gospel")), topic_or_title="penguins")
    assert deck.title == "A classic title about penguins"


def test_a_dutch_talk_gets_no_classic_titles_to_weigh(schema):
    model = FakeModel(change=_writes("Waarom ik bij een pinguïnsekte ging"))
    deck = _talk(model, topic_or_title="waarom ik bij een pinguinsekte ging", language="nl")
    assert (deck.title, deck.language) == ("Waarom ik bij een pinguïnsekte ging", "nl")
    assert "not translated" in _spine_schema(model.requests[0])["title"]["description"]
    model = FakeModel(change=_writes("De Pinguïnsamenzwering"))
    deck = _talk(model, topic_or_title="pinguïns", language="nl")
    assert (deck.title, deck.topic_or_title.read_as) == ("De Pinguïnsamenzwering", "topic")
    (request,) = model.requests
    assert not any(line.startswith("Classic") for line in _lines(request))
    assert "own_title" not in _spine_schema(request)
    assert "in Dutch" in _spine_schema(request)["title"]["description"]


def test_the_same_seed_gives_the_same_talk_on_a_topic_or_title(schema):
    for typed, written in ((TYPED_TITLE, FIXED_TITLE), ("penguins", "The Penguin Gospel")):
        talk = _talk(FakeModel(change=_writes(written)), int_seed=3, topic_or_title=typed).to_json()
        assert _talk(FakeModel(change=_writes(written)), int_seed=3, topic_or_title=typed).to_json() == talk
        again = _talk(FakeModel(change=_writes(written)), int_seed=3, parallel=False, topic_or_title=typed)
        assert again.to_json() == talk


def test_a_recorded_talk_on_a_topic_or_title_can_be_made_again(schema, tmp_path):
    cassette = tmp_path / "talk.json"
    record = FakeModel(change=_writes("The Penguin Gospel", "The Penguin Gospel"))
    recorded = _talk(llm.ReplayProvider(cassette, record=record), int_seed=5, topic_or_title="penguins")
    replayed = _talk(llm.ReplayProvider(cassette), int_seed=5, topic_or_title="penguins")
    assert replayed.to_json() == recorded.to_json()


@pytest.mark.parametrize("writer", ["in order", "alphabetically", "field by field"])
def test_a_streamed_talk_starts_with_the_title_it_settles_on(schema, writer):
    def model():
        change = _writes(FIXED_TITLE)
        if writer == "alphabetically":
            return AlphabeticalModel(change=change)
        if writer == "field by field":
            return SlowModel(change=lambda answer: (change(answer), _flat(answer)))
        return SlowModel(change=change)

    streaming = model()
    stream = generator.stream_talk(
        "fake", NUM_SLIDES, topic_or_title=TYPED_TITLE, presenter="Ann Example", int_seed=1, llm=streaming
    )
    started = next(stream)
    assert isinstance(started, TalkStarted) and not streaming.done.is_set()  # (while the model still writes)
    assert started.title == FIXED_TITLE
    assert started.topic_or_title == TopicOrTitle(text=TYPED_TITLE, read_as="title")
    streaming.go_on.set()
    *_, finished = list(stream)
    at_once = model()
    at_once.go_on.set()
    assert finished.deck.to_json() == _talk(at_once, topic_or_title=TYPED_TITLE).to_json()
