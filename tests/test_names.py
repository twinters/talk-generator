"""Offline tests of the presenter's names (talkgenerator.names): the styles, talkgenerator's own pack of names, what a
name has to be to go on a title slide, and talks whose language model names the presenter in the same request, or
whose name talkgenerator makes up instead.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images.
"""

import json
import re

import pytest

from talkgenerator import generator, llm, names, personas, runtime_checker
from talkgenerator.models.events import TalkFinished, TalkStarted
from talkgenerator.plan.prompt import SPINE
from talkgenerator.schema.content_generators import full_name_generator
from talkgenerator.util import image_util, os_util, random_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _jpeg, fake_schema


@pytest.fixture
def schema(monkeypatch):
    """The fake schema, with images that are found at example.com (whole, or probed, while a talk streams)."""
    jpeg = _jpeg()
    fetch = image_util.fetch_image

    def fetch_fake(url):
        return jpeg if url.startswith("https://example.com/") else fetch(url)

    monkeypatch.setattr(image_util, "fetch_image", fetch_fake)
    monkeypatch.setattr(image_util, "probe", lambda url: fetch_fake(url) is not None)
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _deck(model, int_seed=1, topic="cats", **options):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake", slides=NUM_SLIDES, topic=topic, int_seed=int_seed, save_ppt=False, llm=model, **options
    )
    return slide_deck.to_deck(schema_name="fake")


def _naming(model):
    """Calls a fake model's answer gets a presenter_name, as named."""

    def name(answer):
        answer[SPINE]["presenter_name"] = model

    return name


def _spine(request):
    """The fields of the spine a request asks for, in the response schema."""
    return request.json_schema["properties"][SPINE]["properties"]


def _asked(request):
    """The style of the name a request asks for (None: none)."""
    field = _spine(request).get("presenter_name")
    if field is None:
        return None
    (style,) = [
        name for name, style in names.STYLES.items() if style.asked and field["description"].startswith(style.asked)
    ]
    return style


def _pack_names(topic, *styles):
    return {name for entry in names.pack() if entry.style in styles and entry.fits([topic]) for name in entry.names}


# THE STYLES


def test_a_talk_may_have_the_styles_it_asks_for_in_any_order():
    assert names.styles() == names.DEFAULT_STYLES == ("pun", "fun_surname", "famous_pun")
    assert names.styles("classic, pun") == names.styles(["pun", "classic"]) == ("pun", "classic")
    assert names.styles("") == names.styles([]) == ()
    with pytest.raises(ValueError, match="There's no name style 'custom'; there are pun, fun_surname"):
        names.styles("pun,custom")


def test_the_styles_are_listed_for_a_settings_menu():
    listed = names.catalog()
    assert [style["name"] for style in listed] == ["pun", "fun_surname", "famous_pun", "classic"]
    assert all(style["label"] and style["description"] for style in listed)
    assert [style["name"] for style in listed if style["default"]] == list(names.DEFAULT_STYLES)


# TALKGENERATOR'S OWN NAMES


def test_the_pack_has_names_that_go_on_a_title_slide():
    pack = names.pack()
    assert {entry.style for entry in pack} == {"pun", "fun_surname", "famous_pun"}
    every_name = [name for entry in pack for name in entry.names]
    assert len(every_name) == len(set(every_name)), "a name is in the pack twice"
    for entry in pack:
        assert entry.topic and entry.words and entry.names, entry
        for name, plays_on in zip(entry.names, entry.plays_on, strict=True):
            assert names.clean(name) == name, name
            assert not re.match(r"(Dr|Prof|Professor|Doctor)\b", name), f"{name}: titles come from the jobs"
            # A pun says what it plays on, which the language model is shown; a fun surname is plain to see
            assert bool(plays_on) == (entry.style != "fun_surname"), name
    with open(os_util.to_actual_file(names.PACK_FILE), encoding="utf-8") as file:
        data = json.load(file)
    for style in ("pun", "fun_surname", "famous_pun"):
        for entry in data[style]:  # in the singular and in lower case, as they're matched
            assert all(word == word.lower().strip() for word in entry["words"]), entry["topic"]


def test_the_pack_knows_a_topic_by_its_words():
    def topics_of(topic):
        return {(entry.style, entry.topic) for entry in names.pack() if entry.fits([topic])}

    assert ("pun", "birds") in topics_of("geese")  # (the singular: goose)
    assert ("pun", "medicine") in topics_of("Medicine")
    assert ("pun", "sweets") in topics_of("ice cream")  # (a phrase)
    assert topics_of("a plant that won't die") == {("pun", "gardening")}  # (not dice)
    assert topics_of("zxqv") == set()


def test_a_talk_without_a_language_model_gets_a_name_of_the_pack_for_its_topic():
    name = names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(1))
    assert name in _pack_names("cats", *names.DEFAULT_STYLES)
    assert names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(1)) == name  # (the same seed)
    assert names.from_pack(["cats"], ("fun_surname",), random_util.Rng(1)) == "Martha Whiskerton"


def test_a_talk_without_names_in_the_pack_gets_a_classic_name():
    rng = random_util.Rng(2)
    assert names.from_pack(["zxqv"], names.DEFAULT_STYLES, rng) == names.classic(rng)
    assert names.from_pack(["cats"], ("classic",), rng) == names.classic(rng)
    assert names.from_pack(["cats"], (), rng) == names.classic(rng)


def test_a_seed_keeps_the_classic_name_it_had_before_there_were_styles():
    with random_util.use(random_util.Rng(7).child("presenter")):
        before = full_name_generator()
    assert names.classic(random_util.Rng(7)) == before


# WHAT A NAME HAS TO BE


@pytest.mark.parametrize(
    "name",
    ["Prof. Anna Tomy", "Vincent van Goat", "Chuck O'Late", "Hal Apeño", "Sockrates", "Dr. Jean-Luc Pastry"],
)
def test_a_name_goes_on_the_title_slide(name):
    assert names.clean(f'  "{name}"\n') == name


@pytest.mark.parametrize(
    "written",
    [
        None,
        42,
        "",
        "Prof. Anna Tomy of the Royal Academy of Feline Arts",  # too long (a name isn't cut)
        "Dr. {presenter}",
        "Presenter Name",
        "[Your name]",
        "Dr. Anna Tomy, PhD",
        "R2-D2",
        "Elon Muskrat",
        "Adolf Hitchhiker",
        "Ivan Stalinski",
        "Taylor Swiftly",
        "Donald Trumpet",
        "Pol Potter",
        "Dr. Marie Curie",  # (a famous name as it is: the pack bends hers)
        "A. B.",
    ],
)
def test_a_name_that_wont_do_is_turned_down(written):
    assert names.clean(written) is None


@pytest.mark.parametrize(
    "written",
    [
        "Umbrella Chomsky",  # (a free model's, for a keynote on umbrellas: Noam Chomsky's surname is his alone)
        "Dr. Gnome Chomsky",
        "Oprah Windfrey",
        "Dalai Llama",
        "Kanye Vest",
        "Noam Chompsky",  # (a surname bent, after the first name)
        "Gordon Hamsay",
        "Ryan Goosling",
        "Benedict Cucumberbatch",
        "Mark Zuckerbird",
        "Sir David Attenburrow",
        "Harrison Fjord",
        "Prof. Taylor Q. Swiftly",
        "Tailor Swift",  # (a first name bent, before the surname)
        "Bread Pitt",
        "Hairy Styles",
        "Dr. Bill Gates",  # (a real name as it is)
        "Mary Berry",
    ],
)
def test_a_pun_on_a_famous_living_person_is_turned_down(written):
    # (a famous-name pun is on a historical figure who died long ago: docs/v5-plan.md, section 5.10)
    assert names.clean(written) is None
    assert names.real_person(f"a portrait of {written} in the rain") is not None  # (nor drawn in a picture)


@pytest.mark.parametrize(
    "name",
    [
        "Dr. Emma Swift",  # (an ordinary surname, which a famous living person has too)
        "Linda Gates",
        "Prof. Sarah Cook",
        "Jill Gates",  # (an ordinary first name, a letter off a famous living person's)
        "Dr. Tim Cookson",  # (an ordinary surname, which starts like a famous living person's)
        "Tom Banks",
        "Stephen Kingsley",
        "Dr. Greta Gosling",  # (a word, for a talk on geese, that a famous living person's surname is too)
        "Prof. Anna Streep",  # (a Dutch stripe)
        "Albert Einstone",  # (historical figures who died long ago)
        "Dr. Leonardo da Stone",
        "Hamilton Partnership",
        "Ada Lovefern",
    ],
)
def test_a_name_that_shares_a_word_with_a_famous_living_person_s_goes(name):
    assert names.clean(name) == name
    assert names.real_person(f"{name} riding a camel") is None


def test_every_ordinary_name_goes_on_a_title_slide():
    # (the classic names' 18,839 surnames and 2,297 first names: but a dictator's, and Trump, a surname of its own too)
    with open(os_util.to_actual_file(names.CLASSIC_NAMES_FILE), encoding="utf-8") as file:
        grammar = json.load(file)
    turned_down = [surname for surname in grammar["last_name"] if names.clean(f"Linda {surname}") is None]
    assert turned_down == ["Mao", "Trump"]
    first_names = grammar["male_name"] + grammar["female_name"]
    assert [first for first in first_names if names.clean(f"{first} Hivesworth") is None] == []


def test_a_famous_name_pun_is_asked_for_on_someone_who_died_long_ago():
    asked = names.STYLES["famous_pun"].asked
    assert "one famous historical figure who died long ago" in asked
    assert "never the name of anyone alive today (however old or famous)" in asked
    assert "died long ago" in names.STYLES["famous_pun"].plays_on


def test_a_copy_of_an_example_is_turned_down():
    request = names.NameRequest("pun", (names.Example("Anna Tomy", "medicine", "anatomy"),))
    assert names.clean("Prof. Anna Tomy", request) is None
    assert names.clean("Prof. Anna Tomy") == "Prof. Anna Tomy"


def test_the_examples_are_for_other_topics_than_the_talks():
    for seed in range(20):
        request = names.Naming.of(["pun"], ["medicine"], random_util.Rng(seed), written=True).request
        assert request is not None and len(request.examples) == 2
        assert not {example.name for example in request.examples} & _pack_names("medicine", "pun")
        assert all(example.plays_on for example in request.examples)  # (what a pun plays on, for the model)
    first, second = (names.Naming.of(["pun"], ["cats"], random_util.Rng(seed), True).request for seed in (1, 2))
    assert first != second  # (the dice pick them)


def test_a_name_is_asked_for_in_the_talks_language():
    examples = (
        names.Example("Albert Einstone", "geology", "Albert Einstein"),
        names.Example("Linda Hivesworth", "bees"),
    )
    request = names.NameRequest("famous_pun", examples)
    description = request.description("nl")
    assert description.startswith(names.STYLES["famous_pun"].asked)
    assert "such as 'Albert Einstone' (Albert Einstein) for geology or 'Linda Hivesworth' for bees" in description
    assert "in Dutch, with wordplay that works in Dutch" in description
    assert description.endswith("(at most 40 characters)")
    assert "wordplay" not in request.description("en")


# TALKS


def test_the_language_model_names_the_presenter_in_the_same_request(schema):
    model = FakeModel(change=_naming("Prof. Clawdette Purrkins"))
    deck = _deck(model, name_styles="pun")

    assert len(model.requests) == 1
    assert deck.presenter == "Prof. Clawdette Purrkins"
    assert deck.slides[0].elements[1].text.endswith("Prof. Clawdette Purrkins, The presenter job")
    request = model.requests[0]
    properties = _spine(request)
    spine = ["unsafe_topic", "thesis", "title", "name_plays_on", "presenter_name", "presenter_job"]
    assert list(properties) == spine
    assert _asked(request) == "pun"
    # (What the name plays on first: it comes before the name in the schema's order and in alphabetical order, in
    # which some free models write the answer)
    assert sorted(spine)[:3] == ["name_plays_on", "presenter_job", "presenter_name"]
    assert properties["name_plays_on"]["description"].startswith(names.STYLES["pun"].plays_on)
    assert "agreeing with presenter_name (a Prof. is a professor" in properties["presenter_job"]["description"]
    prompt = request.messages[0].content
    assert f"- presenter_name: {properties['presenter_name']['description']}" in prompt
    assert f"- name_plays_on: {properties['name_plays_on']['description']}" in prompt
    assert "write the title, the presenter's name and job and every slide in English" in prompt


def test_the_talks_seed_picks_the_style_among_the_chosen_ones(schema):
    def styles_asked(seeds, **options):
        asked = []
        for seed in seeds:
            model = FakeModel()
            _deck(model, int_seed=seed, **options)
            asked.append(_asked(model.requests[0]))
        return asked

    assert set(styles_asked(range(1, 13))) == {"pun", "fun_surname", "famous_pun"}
    assert set(styles_asked(range(1, 5), name_styles=["famous_pun"])) == {"famous_pun"}
    assert styles_asked([1, 2], name_styles=[]) == [None, None]  # (classic names, which the model doesn't write)


def test_a_talk_whose_dice_pick_classic_names_gets_one(schema):
    model = FakeModel(change=_naming("Prof. Clawdette Purrkins"))
    deck = _deck(model, int_seed=3, name_styles="classic")
    assert _asked(model.requests[0]) is None
    assert "presenter_name" not in model.requests[0].messages[0].content
    assert deck.presenter == names.classic(random_util.Rng(3))


@pytest.mark.parametrize(
    "written", ["The presenter name", "{presenter}", "Elon Muskrat", "Umbrella Chomsky", "Dr. Kitty Litter" * 3, 42]
)
def test_a_name_that_wont_do_is_made_up_instead(schema, written):
    deck = _deck(FakeModel(change=_naming(written)), name_styles="pun")
    assert deck.presenter == names.from_pack(["cats"], ("pun",), random_util.Rng(1))
    assert deck.presenter in _pack_names("cats", "pun")


def test_a_given_name_goes_first_and_no_name_is_asked_for(schema):
    model = FakeModel(change=_naming("Prof. Clawdette Purrkins"))
    deck = _deck(model, presenter="Ann Example")
    assert deck.presenter == "Ann Example"
    request = model.requests[0]
    assert _asked(request) is None and "presenter_name" not in request.messages[0].content
    assert "Ann Example" not in request.system + json.dumps(request.model_dump())


def _nudge(seed):
    """The name nudge of the persona a talk with this seed gets (see talkgenerator.personas)."""
    return personas.pick(None, random_util.Rng(seed)).nudge


def test_a_talk_whose_model_fails_gets_a_name_of_talkgenerators_own(schema):
    deck = _deck(FakeModel(fail=llm.RateLimited("free quota used up")))
    assert deck.presenter == names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(1), _nudge(1))
    assert deck.presenter in _pack_names("cats", *names.DEFAULT_STYLES)


def test_a_classic_talk_gets_a_name_of_the_pack_or_a_classic_one(schema):
    expected = names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(2), _nudge(2))
    assert _deck(None, int_seed=2).presenter == expected
    assert _deck(None, int_seed=2, topic="zxqv").presenter == names.classic(random_util.Rng(2))
    assert _deck(None, int_seed=2, name_styles="classic").presenter == names.classic(random_util.Rng(2))


def test_a_model_that_declines_leaves_no_name(schema):
    def decline(answer):
        answer[SPINE]["presenter_name"] = "Prof. Clawdette Purrkins"

    class Declining(FakeModel):
        def complete(self, request):
            return super().complete(request).model_copy(update={"finish": "refused"})

    deck = _deck(Declining(change=decline), name_styles="pun")
    assert deck.presenter == names.from_pack(["cats"], ("pun",), random_util.Rng(1))


def test_the_order_of_the_styles_doesnt_change_the_talk(schema):
    assert _deck(FakeModel(), int_seed=4, name_styles=["pun", "classic"]).to_json() == (
        _deck(FakeModel(), int_seed=4, name_styles="classic, pun").to_json()
    )


def test_a_recorded_talk_keeps_its_name(schema, tmp_path):
    cassette = tmp_path / "talk.json"
    model = FakeModel(change=_naming("Prof. Tabby Cattington"))
    recorded = _deck(llm.ReplayProvider(cassette, record=model), int_seed=5)
    replayed = _deck(llm.ReplayProvider(cassette), int_seed=5)
    assert replayed.presenter == recorded.presenter == "Prof. Tabby Cattington"
    assert replayed.slides == recorded.slides


@pytest.mark.parametrize("llm_", ["fake", "none"], ids=["planned", "classic"])
@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_a_streamed_talk_starts_with_the_name_its_deck_has(schema, llm_, parallel):
    def model():
        return FakeModel(change=_naming("Dr. Whiskers McPurrson")) if llm_ == "fake" else "none"

    events = list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", int_seed=3, llm=model(), parallel=parallel))
    started, finished = events[0], events[-1]
    assert isinstance(started, TalkStarted) and isinstance(finished, TalkFinished)
    assert started.presenter == finished.deck.presenter
    assert finished.deck.to_json() == _deck(model(), int_seed=3, parallel=parallel).to_json()
    if llm_ == "fake":
        assert started.presenter == "Dr. Whiskers McPurrson"


def test_a_dutch_talk_asks_for_a_dutch_name(schema):
    model = FakeModel(change=_naming("Prof. Kat Apult"))
    deck = _deck(model, language="nl")
    request = model.requests[0]
    assert "with wordplay that works in Dutch" in _spine(request)["presenter_name"]["description"]
    assert "write the title, the presenter's name and job and every slide in Dutch" in request.messages[0].content
    assert deck.presenter == "Prof. Kat Apult"
    assert deck.slides[0].elements[1].text.split(" Prof. Kat Apult")[0] in (
        "Door",
        "Een presentatie van",
        "Gepresenteerd door",
    )


def test_a_style_there_isnt_is_turned_down(schema):
    with pytest.raises(ValueError, match="no name style 'nope'"):
        _deck(None, name_styles="pun,nope")
    with pytest.raises(ValueError, match="no name style 'nope'"):
        list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", name_styles=["nope"]))


def test_the_command_line_takes_name_styles(monkeypatch):
    parser = generator.get_argument_parser()
    args = parser.parse_args(["--topic", "cats", "--name_styles", "classic,pun", "--print_logs", "false"])
    assert args.name_styles == ("pun", "classic")
    assert parser.parse_args([]).name_styles is None
    with pytest.raises(SystemExit):
        parser.parse_args(["--name_styles", "nope"])

    given = {}
    monkeypatch.setattr(runtime_checker, "check_runtime_environment", lambda: True)
    monkeypatch.setattr(generator, "_generate_presentation", lambda **options: given.update(options))
    generator.generate_presentation_using_cli_arguments(args)
    assert given["name_styles"] == ("pun", "classic")
