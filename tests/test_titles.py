"""Offline tests of what's typed for a talk, which can be its topic or its title (talkgenerator.titles): talkgenerator's
guess, the topics it gives, a typed title that the language model fixes (or rewrites), the classic titles a model may
pick, and classic talks on a topic_or_title. Talks a language model writes are in test_llm_talks and test_streaming.
"""

import pytest

from talkgenerator import generator, titles
from talkgenerator.models.deck import TopicOrTitle
from talkgenerator.models.events import TalkStarted
from talkgenerator.sources import wikihow, word_frequency
from talkgenerator.util import image_util, random_util
from tests.test_llm_talks import NUM_SLIDES, _jpeg, fake_schema


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

TOPICS = ["penguins", "artificial intelligence", "medieval cheese making", "cats, dogs, birds, fish", "Cats are liquid"]
TITLES = [
    "Why I Joined a Penguin Cult",
    "why i joind a pengiun cult",  # (misspelled)
    "How to train your dragon",
    "The French Revolution",  # (a topic too, but it starts like a title)
    "My dog",
    "Are penguins real?",
    "Penguins!",
    '"Ten things you never knew about cheese"',
]


@pytest.mark.parametrize("typed", TOPICS)
def test_a_few_words_are_guessed_to_be_a_topic(typed):
    assert titles.guess(typed) == titles.TOPIC


@pytest.mark.parametrize("typed", TITLES)
def test_four_words_a_title_s_start_or_end_are_guessed_to_be_a_title(typed):
    assert titles.guess(typed) == titles.TITLE


def test_titles_start_like_titles_in_the_talk_s_language_too():
    assert titles.guess("Het weer") == titles.TOPIC
    assert titles.guess("Het weer", "nl") == titles.TITLE
    assert titles.guess("Waarom katten", "nl") == titles.TITLE
    assert titles.guess("Why cats", "nl") == titles.TITLE  # (English goes for every language)


def test_the_topics_come_from_a_title_s_rarest_word_and_otherwise_from_what_was_typed():
    assert titles.topics_from("Why I Joined a Penguin Cult") == ["Penguin"]
    assert titles.topics_from('  "My trip to Zorblaxia"  ') == ["Zorblaxia"]  # (unknown: the rarest)
    assert titles.topics_from("penguins") == ["penguins"]
    assert titles.topics_from("cats, dogs") == ["cats", "dogs"]
    assert titles.topics_from("medieval  cheese making") == ["medieval cheese making"]


def test_a_misspelled_word_doesnt_become_the_topic():
    # A misspelling is a word no language knows, so the rarest: it's taken as the word it's most likely to be
    assert titles.topics_from("why i joind a pengiun cult") == ["penguin"]
    assert word_frequency.get_rarest_word("why i joind a pengiun cult") == "joind"  # (as before, without the fix)


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
        "",
    ],
)
def test_a_typed_title_rewritten_isnt(written):
    assert not titles.recognisable("Why I Joined a Penguin Cult", written)


def _settled(spine, typed="why i joind a pengiun cult", written=True):
    titling = titles.Titling.of(typed, written=written)
    return titling.settle(spine, lambda: "A classic title")


def test_a_title_the_model_reads_keeps_its_wording_with_its_slips_fixed():
    title, reading = _settled({"reads_as": "title", "title": "Why I Joined a Penguin Cult"})
    assert title == "Why I Joined a Penguin Cult"
    assert reading == TopicOrTitle(text="why i joind a pengiun cult", read_as="title", by="language model")


def test_a_title_the_model_rewrites_stays_as_typed():
    title, _ = _settled({"reads_as": "title", "title": "My Life Among the Penguins: A Cult Story"})
    assert title == "why i joind a pengiun cult"
    title, _ = _settled({"reads_as": "title"})  # (no title at all)
    assert title == "why i joind a pengiun cult"


def test_a_topic_the_model_reads_gets_the_model_s_title_or_else_a_classic_one():
    title, reading = _settled({"reads_as": "topic", "title": "The Penguin Gospel"}, typed="penguin cults")
    assert (title, reading.read_as, reading.by) == ("The Penguin Gospel", "topic", "language model")
    title, _ = _settled({"reads_as": "topic", "title": "{seed}"}, typed="penguin cults")  # (template code)
    assert title == "A classic title"


@pytest.mark.parametrize("said", [None, "", "a title", "both", 1, True])
def test_when_the_model_doesnt_say_how_it_read_it_talkgenerator_guesses(said):
    _, reading = _settled({"reads_as": said, "title": "Why I Joined a Penguin Cult"})
    assert (reading.read_as, reading.by) == ("title", "guess")
    title, reading = _settled({"reads_as": said, "title": "The Penguin Gospel"}, typed="penguin cults")
    assert (title, reading.read_as, reading.by) == ("The Penguin Gospel", "topic", "guess")


def test_the_model_s_reading_counts_however_it_s_written():
    _, reading = _settled({"reads_as": " Title ", "title": "Why I Joined a Penguin Cult"}, typed="penguin cults")
    assert (reading.read_as, reading.by) == ("title", "language model")


def test_without_a_language_model_the_guess_decides_and_a_title_stays_as_typed():
    # (Whatever a spine says: there's no model, so nothing it wrote counts)
    title, reading = _settled({"reads_as": "topic", "title": "The Penguin Gospel"}, written=False)
    assert (title, reading.read_as, reading.by) == ("why i joind a pengiun cult", "title", "guess")
    title, reading = _settled({}, typed="penguins", written=False)
    assert (title, reading.read_as, reading.by) == ("A classic title", "topic", "guess")


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


def test_classic_titles_that_fail_or_repeat_are_left_out():
    def crash(context):
        raise RuntimeError("a source that broke")

    rng = next(random_util.Rng(seed) for seed in range(100) if _wanted(random_util.Rng(seed)) == 3)
    drawn = titles.candidates(
        [_counting("same", [], "How to Fly"), crash, _counting("none", [], ""), _counting("same", [], "HOW TO FLY")],
        "penguins",
        rng,
    )
    assert drawn == ("How to Fly",)


def _wanted(rng):
    with random_util.use(rng.child("title", "candidates")):
        return random_util.randint(1, 3)


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
    _, slide_deck, _ = generator.generate_presentation(
        schema="fake", slides=NUM_SLIDES, presenter="Ann Example", int_seed=1, save_ppt=False, llm="none", **options
    )
    return slide_deck.to_deck()


def test_a_classic_talk_on_a_title_keeps_it_as_typed(schema):
    deck = _classic_talk(topic_or_title="Why I joined a penguin cult")
    assert deck.title == "Why I joined a penguin cult"
    assert deck.topics == ("penguin",)
    assert deck.topic_or_title == TopicOrTitle(text="Why I joined a penguin cult", read_as="title", by="guess")
    assert deck.slides[0].elements[0].text == "Why I joined a penguin cult"


def test_a_classic_talk_on_a_topic_gets_a_classic_title(schema):
    deck = _classic_talk(topic_or_title="  penguins ")
    assert deck.title == "A classic title about penguins"
    assert deck.topics == ("penguins",)
    assert deck.topic_or_title == TopicOrTitle(text="penguins", read_as="topic", by="guess")
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
