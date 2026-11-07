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
        "",
    ],
)
def test_a_typed_title_rewritten_isnt(written):
    assert not titles.recognisable("Why I Joined a Penguin Cult", written)


def _settled(spine, typed="why i joind a pengiun cult", written=True):
    titling = titles.Titling.of(typed, written=written)
    return titling.settle(spine, lambda: "A classic title")


def test_a_title_the_model_reads_keeps_its_wording_with_its_slips_fixed():
    title, reading = _settled({"input_is": "title", "title": "Why I Joined a Penguin Cult"})
    assert title == "Why I Joined a Penguin Cult"
    assert reading == TopicOrTitle(text="why i joind a pengiun cult", read_as="title", by="language model")


def test_a_title_the_model_rewrites_stays_as_typed():
    title, _ = _settled({"input_is": "title", "title": "My Life Among the Penguins: A Cult Story"})
    assert title == "why i joind a pengiun cult"
    title, _ = _settled({"input_is": "title"})  # (no title at all)
    assert title == "why i joind a pengiun cult"


def test_a_topic_the_model_reads_gets_the_model_s_title_or_else_a_classic_one():
    title, reading = _settled({"input_is": "topic", "title": "The Penguin Gospel"}, typed="penguin cults")
    assert (title, reading.read_as, reading.by) == ("The Penguin Gospel", "topic", "language model")
    title, _ = _settled({"input_is": "topic", "title": "{seed}"}, typed="penguin cults")  # (template code)
    assert title == "A classic title"


@pytest.mark.parametrize("said", [None, "", "a title", "both", 1, True])
def test_when_the_model_doesnt_say_how_it_read_it_talkgenerator_guesses(said):
    _, reading = _settled({"input_is": said, "title": "Why I Joined a Penguin Cult"})
    assert (reading.read_as, reading.by) == ("title", "guess")
    title, reading = _settled({"input_is": said, "title": "The Penguin Gospel"}, typed="penguin cults")
    assert (title, reading.read_as, reading.by) == ("The Penguin Gospel", "topic", "guess")


def test_the_model_s_reading_counts_however_it_s_written():
    _, reading = _settled({"input_is": " Title ", "title": "Why I Joined a Penguin Cult"}, typed="penguin cults")
    assert (reading.read_as, reading.by) == ("title", "language model")


def test_without_a_language_model_the_guess_decides_and_a_title_stays_as_typed():
    # (Whatever a spine says: there's no model, so nothing it wrote counts)
    title, reading = _settled({"input_is": "topic", "title": "The Penguin Gospel"}, written=False)
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


# TALKS A LANGUAGE MODEL WRITES

TYPED_TITLE = "why i joind a pengiun cult"
FIXED_TITLE = "Why I Joined a Penguin Cult"


def _reads(input_is, title=None):
    """A change to the fake model's answer: how it read what was typed, and the title it wrote."""

    def change(answer):
        answer[SPINE][titles.INPUT_IS] = input_is
        if title is not None:
            answer[SPINE]["title"] = title

    return change


def _talk(model, int_seed=1, parallel=True, **options):
    _, slide_deck, _ = generator.generate_presentation(
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


def test_the_model_is_asked_whether_what_was_typed_is_a_topic_or_a_title(schema):
    model = FakeModel()
    _talk(model, topic_or_title=TYPED_TITLE)
    (request,) = model.requests
    lines = _lines(request)
    assert lines[0] == f"Typed: {TYPED_TITLE} (the user's input: the talk's topic or its title; say which in input_is)"
    assert lines[1].startswith('Classic titles, for a topic: "A classic title about penguin"')
    assert not any(line.startswith(("Topic:", "Title:")) for line in lines)
    spine = _spine_schema(request)
    assert list(spine)[:5] == ["unsafe_topic", "input_is", "thesis", "own_title", "title"]
    assert spine["input_is"]["enum"] == ["topic", "title"]
    assert min(spine) == "input_is"  # (first, also for a model that writes the fields in alphabetical order)
    assert "Ann Example" not in request.system + json.dumps(request.model_dump())


def test_a_topic_or_title_given_as_such_is_asked_for_as_before(schema):
    model = FakeModel()
    _talk(model, topic="penguins")
    lines = _lines(model.requests[0])
    assert lines[:2] == ["Topic: penguins", "Title: come up with one"]
    assert lines[2].startswith("Language: write the title, the presenter's job and every slide in English")
    spine = _spine_schema(model.requests[0])
    assert "input_is" not in spine and "own_title" not in spine
    assert spine["title"]["description"] == "the talk's title, in English (at most 80 characters)"


def test_a_title_the_model_reads_keeps_its_words_with_its_slips_fixed(schema):
    deck = _talk(FakeModel(change=_reads("title", FIXED_TITLE)), topic_or_title=TYPED_TITLE)
    assert deck.title == deck.slides[0].elements[0].text == FIXED_TITLE
    assert deck.topic_or_title == TopicOrTitle(text=TYPED_TITLE, read_as="title", by="language model")
    assert deck.topics == ("penguin",)  # (a misspelling isn't the topic)
    assert all("Planned:" in slide.notes for slide in deck.slides)


def test_a_talk_whose_model_rewrites_the_typed_title_keeps_it_as_typed(schema):
    deck = _talk(FakeModel(change=_reads("title", "Penguins: My Cult Years")), topic_or_title=TYPED_TITLE)
    assert deck.title == TYPED_TITLE


def test_a_topic_the_model_reads_gets_the_model_s_title(schema):
    deck = _talk(FakeModel(change=_reads("topic", "The Penguin Gospel")), topic_or_title="penguins")
    assert (deck.title, deck.topics) == ("The Penguin Gospel", ("penguins",))
    assert deck.topic_or_title == TopicOrTitle(text="penguins", read_as="topic", by="language model")


def test_a_title_the_guess_missed_is_read_by_the_model(schema):
    # (Three words, without a title's start or end: talkgenerator would take it for a topic)
    deck = _talk(FakeModel(change=_reads("title", "Cats Are Liquid")), topic_or_title="cats are liquid")
    assert (deck.title, deck.topic_or_title.read_as, deck.topic_or_title.by) == (
        "Cats Are Liquid",
        "title",
        "language model",
    )
    assert deck.topics == ("cats are liquid",)  # (settled before the model was asked: by the guess)


def test_when_the_model_doesnt_say_the_guess_reads_it(schema):
    deck = _talk(FakeModel(), topic_or_title=FIXED_TITLE)  # (its input_is: "The input is")
    assert (deck.title, deck.topic_or_title.read_as, deck.topic_or_title.by) == (FIXED_TITLE, "title", "guess")
    deck = _talk(FakeModel(), topic_or_title="penguins")
    assert (deck.title, deck.topic_or_title.by) == ("The title", "guess")


def test_a_model_that_fails_leaves_a_classic_talk_to_the_guess(schema):
    deck = _talk(FakeModel(fail=llm.RateLimited("free quota used up")), topic_or_title=TYPED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as, deck.topic_or_title.by) == (TYPED_TITLE, "title", "guess")
    deck = _talk(FakeModel(fail=llm.RateLimited("free quota used up")), topic_or_title="penguins")
    assert deck.title == "A classic title about penguins"


class _Declining(FakeModel):
    """Writes the talk, then declines (what it wrote isn't to be used)."""

    def complete(self, request):
        return super().complete(request).model_copy(update={"finish": "refused"})


def test_a_model_that_declines_leaves_it_to_the_guess(schema):
    deck = _talk(_Declining(change=_reads("topic", "The Penguin Gospel")), topic_or_title=FIXED_TITLE)
    assert (deck.title, deck.topic_or_title.read_as, deck.topic_or_title.by) == (FIXED_TITLE, "title", "guess")


def test_a_dutch_talk_on_a_typed_title_has_no_classic_titles_to_weigh(schema):
    model = FakeModel(change=_reads("title", "Waarom ik bij een pinguïnsekte ging"))
    deck = _talk(model, topic_or_title="waarom ik bij een pinguinsekte ging", language="nl")
    assert (deck.title, deck.language) == ("Waarom ik bij een pinguïnsekte ging", "nl")
    (request,) = model.requests
    assert not any(line.startswith("Classic titles") for line in _lines(request))
    assert "own_title" not in _spine_schema(request)
    assert "in Dutch" in _spine_schema(request)["title"]["description"]


def test_the_same_seed_gives_the_same_talk_on_a_topic_or_title(schema):
    def model():
        return FakeModel(change=_reads("title", FIXED_TITLE))

    talk = _talk(model(), int_seed=3, topic_or_title=TYPED_TITLE).to_json()
    assert _talk(model(), int_seed=3, topic_or_title=TYPED_TITLE).to_json() == talk
    assert _talk(model(), int_seed=3, parallel=False, topic_or_title=TYPED_TITLE).to_json() == talk


def test_a_recorded_talk_on_a_topic_or_title_can_be_made_again(schema, tmp_path):
    cassette = tmp_path / "talk.json"
    record = FakeModel(change=_reads("topic", "The Penguin Gospel"))
    recorded = _talk(llm.ReplayProvider(cassette, record=record), int_seed=5, topic_or_title="penguins")
    replayed = _talk(llm.ReplayProvider(cassette), int_seed=5, topic_or_title="penguins")
    assert replayed.to_json() == recorded.to_json()


@pytest.mark.parametrize("writer", ["in order", "alphabetically", "field by field"])
def test_a_streamed_talk_starts_with_the_title_it_settles_on(schema, writer):
    def model():
        change = _reads("title", FIXED_TITLE)
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
    assert started.topic_or_title == TopicOrTitle(text=TYPED_TITLE, read_as="title", by="language model")
    streaming.go_on.set()
    *_, finished = list(stream)
    at_once = model()
    at_once.go_on.set()
    assert finished.deck.to_json() == _talk(at_once, topic_or_title=TYPED_TITLE).to_json()
