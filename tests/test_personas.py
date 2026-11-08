"""Offline tests of talks' personas (talkgenerator.personas): who presents a talk, as its dice pick them (or as it
names them), and how they shape it, with a language model or without: its kinds of slides, its title, its presenter's
name, and the model's voice and angle. The deck and talk.started say which persona a talk had.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images.
"""

import collections
import dataclasses
import json
import statistics

import pytest

from talkgenerator import generator, llm, names, personas, runtime_checker
from talkgenerator.checks.deck import deck_metrics
from talkgenerator.design import themes
from talkgenerator.images import context as image_context
from talkgenerator.images import profiles
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import Deck, TalkPersona
from talkgenerator.models.events import TalkFinished, TalkStarted
from talkgenerator.plan.prompt import SPINE
from talkgenerator.schema import content_generators, slide_schemas
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.util import image_util, random_util
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


def _prompt(model):
    return model.requests[0].messages[0].content


def _spine(model):
    return model.requests[0].json_schema["properties"][SPINE]["properties"]


def _tags():
    return {tag for generator_ in slide_schemas.slide_generators for tag in generator_.get_tags()}


# THE PERSONAS


def test_every_persona_has_all_it_takes():
    styles = set(names.STYLES) - {names.CLASSIC}
    assert len(personas.PERSONAS) >= 10
    for name, persona in personas.PERSONAS.items():
        assert persona.name == name and persona.label and persona.voice, name
        assert len(persona.angles) >= 3 and len(set(persona.angles)) == len(persona.angles), name
        assert persona.title_hint and persona.name_manner and persona.job_hint, name
        assert len(persona.titles) >= 3, name
        for template in persona.titles:  # (a title about the topic, made offline: no wikiHow or ConceptNet)
            title = personas._templates((template,)).generate({"seed": "penguins"})
            assert title and "Penguins" in title and "{" not in title, (name, template)
            # (also on a topic with an article, as typed: "Finding Your Inner The French Revolution" won't do)
            title = personas._templates((template,)).generate({"seed": "the French Revolution"})
            assert "Inner The" not in title and "The The" not in title and not title.endswith("The"), (name, title)
        assert set(persona.name_styles) <= styles and all(weight > 0 for weight in persona.name_styles.values()), name


def test_personas_weigh_tags_there_are_and_take_no_kind_of_slide_away():
    tags = _tags()
    for name, persona in personas.PERSONAS.items():
        assert set(persona.slides) <= tags, (name, set(persona.slides) - tags)  # (a tag renamed shows here)
        assert not set(persona.slides) & personas.UNWEIGHTED_TAGS, name
        assert all(0.2 <= factor <= 4 for factor in persona.slides.values()), name
        assert any(factor > 1 for factor in persona.slides.values()), name  # (what they favour)
        assert any(factor < 1 for factor in persona.slides.values()), name  # (and what they don't)


def test_personas_move_slides_around_rather_than_change_the_mix():
    # Across the personas, every kind of slide comes up about as often as the formats' own weights say
    named = {tag for persona in personas.PERSONAS.values() for tag in persona.slides}
    for tag in named:
        average = statistics.mean(persona.slides.get(tag, 1.0) for persona in personas.PERSONAS.values())
        assert 0.75 <= average <= 1.35, (tag, average)


def test_a_slide_generator_s_weight_is_the_product_of_its_tags_multipliers():
    historian = personas.persona("medieval_historian")
    assert historian.weight(["history", "quote"]) == pytest.approx(3 * 1.5)
    assert historian.weight(["history", "history"]) == 3  # (a tag counts once)
    assert historian.weight(["title"]) == historian.weight([]) == 1


def test_the_talk_s_seed_picks_its_persona():
    picked = [personas.pick(None, random_util.Rng(seed)) for seed in range(60)]
    assert picked == [personas.pick(None, random_util.Rng(seed)) for seed in range(60)]
    assert picked == [personas.pick("random", random_util.Rng(seed)) for seed in range(60)]
    assert len({persona.name for persona in picked}) >= 10
    assert personas.pick(" Startup_Founder ", random_util.Rng(1)) is personas.PERSONAS["startup_founder"]
    assert personas.pick("none", random_util.Rng(1)) is None
    with pytest.raises(ValueError, match="There's no persona 'nope'; there are random, none, disgraced_professor"):
        personas.pick("nope", random_util.Rng(1))


def test_the_catalog_lists_every_persona():
    assert [entry["name"] for entry in personas.catalog()] == list(personas.PERSONAS)
    assert all(entry["label"] and entry["description"] for entry in personas.catalog())
    assert personas.choices() == ("random", "none", *personas.PERSONAS)


# THE SLIDES THEY FAVOUR


def _picked_tags(persona, seeds=range(150), slides=10, schema_name="default"):
    """How many slides of talks with these seeds got a slide generator with each tag, as the persona weighs them."""
    schema = get_schema(schema_name)
    counted = collections.Counter()
    for seed in seeds:
        for pick in schema._pick_generators(slides, random_util.Rng(seed), "en", persona):
            if pick is not None:
                counted.update(pick.get_tags())
    return counted


def test_a_persona_s_talks_favour_its_kinds_of_slides():
    historian = _picked_tags(personas.persona("medieval_historian"))
    founder = _picked_tags(personas.persona("startup_founder"))
    teacher = _picked_tags(personas.persona("kindergarten_teacher"))
    plain = _picked_tags(None)
    assert historian["timeline"] > 2 * plain["timeline"] and historian["timeline"] > 3 * founder["timeline"]
    assert historian["history"] > founder["history"] * 3
    assert founder["kpi"] > 2 * plain["kpi"] and founder["kpi"] > 5 * historian["kpi"]
    assert founder["funnel"] > 2 * plain["funnel"]
    assert teacher["quiz"] > 2 * plain["quiz"] and teacher["kpi"] < plain["kpi"]
    # The format's caps still hold: at most one timeline in a talk, whoever presents it
    for seed in range(40):
        picks = get_schema("default")._pick_generators(
            10, random_util.Rng(seed), "en", personas.persona("time_traveller")
        )
        assert sum("timeline" in pick.get_tags() for pick in picks if pick is not None) <= 1


def _statements(monkeypatch, **slides):
    """A persona with these multipliers, as the talk names it."""
    monkeypatch.setitem(
        personas.PERSONAS, "tester", dataclasses.replace(personas.PERSONAS["consultant"], name="tester", slides=slides)
    )
    return "tester"


@pytest.mark.parametrize("planned", [True, False], ids=["planned", "classic"])
def test_classic_and_planned_talks_both_favour_the_persona_s_slides(schema, monkeypatch, planned):
    def statements(persona):
        types = []
        for seed in range(1, 5):
            deck = _deck(FakeModel() if planned else None, int_seed=seed, persona=persona)
            types += [slide.type for slide in deck.slides]
        return types.count("large_quote")  # (the fake schema's statements)

    fond = _statements(monkeypatch, statement=25)
    assert statements(fond) > 2 * statements("none") > 0


# THE MODEL'S VOICE AND ANGLE, AND THE TITLE


def test_the_model_writes_in_the_persona_s_voice_on_one_of_its_angles(schema):
    model = FakeModel()
    deck = _deck(model, persona="medieval_historian")
    historian = personas.persona("medieval_historian")
    prompt = _prompt(model)
    assert "\nThe presenter: a medieval historian who sees the Middle Ages in everything\n" in prompt
    (angle,) = [line.removeprefix("The angle: ") for line in prompt.splitlines() if line.startswith("The angle: ")]
    assert angle in historian.angles
    assert deck.persona == TalkPersona(
        name="medieval_historian", label="Medieval historian", voice=historian.voice, angle=angle
    )
    # The seed picks the angle among the persona's
    angles = set()
    for seed in range(1, 13):
        model = FakeModel()
        _deck(model, int_seed=seed, persona="medieval_historian")
        angles.add(_prompt(model).split("The angle: ")[1].splitlines()[0])
    assert angles == set(historian.angles)


def test_a_title_the_model_makes_up_is_like_the_persona_s(schema):
    founder = personas.persona("startup_founder")
    model = FakeModel()
    _deck(model, persona="startup_founder")
    assert (
        _spine(model)["title"]["description"]
        == f"the talk's title, {founder.title_hint}, in English (at most 80 characters)"
    )
    assert f"- title: the talk's title, {founder.title_hint}, in English" in _prompt(model)

    # (and its own title, for what was typed, as the talk's topic)
    model = FakeModel()
    _deck(model, topic=None, topic_or_title="penguin cults", persona="startup_founder")
    assert f"building on it, {founder.title_hint}, spelled right" in _spine(model)["own_title"]["description"]


@pytest.mark.parametrize(
    "options",
    [{"title": "Cats, Explained"}, {"topic": None, "topic_or_title": "Why I Joined a Penguin Cult"}],
    ids=["given", "typed"],
)
def test_a_title_the_talk_has_already_gets_no_hint(schema, options):
    model = FakeModel()
    _deck(model, persona="startup_founder", **options)
    hint = personas.persona("startup_founder").title_hint
    assert hint not in json.dumps(model.requests[0].model_dump())


def test_the_presenter_s_job_is_the_persona_s_kind_of_job(schema):
    # (in place of the job field's example, which free models copied whoever presented)
    model = FakeModel()
    _deck(model, persona="kindergarten_teacher")
    description = _spine(model)["presenter_job"]["description"]
    assert description.startswith("the presenter's grand, made-up job: their role at the kindergarten, made to sound")
    assert "Applied Sock Theory" not in json.dumps(model.requests[0].model_dump())
    assert f"- presenter_job: {description}" in _prompt(model)


def test_a_talk_without_a_persona_tells_the_model_none(schema):
    model = FakeModel()
    deck = _deck(model, persona="none")
    assert "The presenter:" not in _prompt(model) and "The angle:" not in _prompt(model)
    assert _spine(model)["title"]["description"] == "the talk's title, in English (at most 80 characters)"
    assert "such as 'Professor of Applied Sock Theory'" in _spine(model)["presenter_job"]["description"]
    assert deck.persona is None


def test_half_of_a_classic_talk_s_titles_are_its_persona_s():
    fake = fake_schema()
    for persona in personas.PERSONAS.values():
        own = {template.replace("{seed.title}", "Cats") for template in persona.titles}
        made = [fake._title(["cats"], random_util.Rng(seed), persona) for seed in range(60)]
        assert set(made) <= own | {"A classic title about cats"}, persona.name
        assert 15 <= sum(title in own for title in made) <= 45, persona.name
    assert {fake._title(["cats"], random_util.Rng(seed)) for seed in range(10)} == {"A classic title about cats"}


def test_a_classic_talk_s_title_is_one_its_persona_could_give(schema):
    for seed in range(1, 9):
        deck = _deck(None, int_seed=seed)
        persona = personas.persona(deck.persona.name)
        own = {template.replace("{seed.title}", "Cats") for template in persona.titles}
        assert deck.title in own | {"A classic title about cats"}
        assert deck.title == fake_schema()._title(["cats"], random_util.Rng(seed), persona)


# THE THEME, AND THE LOOKS OF ITS PICTURES


def _families(persona, seeds=range(1000)):
    """How often each theme family comes up in random themes of talks with these seeds, as the persona favours them."""
    favoured = persona.themes if persona is not None else None
    return collections.Counter(
        themes.pick(themes.RANDOM, random_util.Rng(seed).child("theme"), True, favoured).family for seed in seeds
    )


def test_personas_favour_theme_families_there_are():
    for name, persona in personas.PERSONAS.items():
        assert persona.themes and set(persona.themes) <= set(themes.FAMILIES), (name, set(persona.themes))
        assert all(0.2 <= factor <= 8 for factor in persona.themes.values()), name
        assert any(factor > 1 for factor in persona.themes.values()), name


def test_a_persona_s_talks_are_in_its_favourite_theme_families_more_often():
    plain = _families(None)
    teacher = _families(personas.persona("kindergarten_teacher"))
    historian = _families(personas.persona("medieval_historian"))
    blogger = _families(personas.persona("conspiracy_blogger"))
    # (about 3 to 4.5 times as often; the weights say 3.7 to 4.6)
    assert teacher["kids"] > 2.5 * plain["kids"] and teacher["hacker terminal"] < plain["hacker terminal"]
    assert historian["vintage paper"] > 2.5 * plain["vintage paper"]
    assert blogger["hacker terminal"] > 2.5 * plain["hacker terminal"]
    assert len(teacher) >= 10  # (and the other families still come up)


def test_across_the_personas_every_theme_family_comes_up_about_as_often():
    def shares(favoured):
        weights = {family.name: family.weight * favoured.get(family.name, 1.0) for family in themes.FAMILIES.values()}
        return {name: weight / sum(weights.values()) for name, weight in weights.items()}

    base = shares({})
    for name in base:
        average = statistics.mean(shares(persona.themes)[name] for persona in personas.PERSONAS.values())
        assert 0.75 <= average / base[name] <= 1.33, (name, average / base[name])


def test_a_theme_the_talk_asks_for_wins_over_its_persona(schema):
    assert _deck(None, theme="neon", persona="kindergarten_teacher").style.family == "neon"
    assert _deck(None, theme="classic", persona="kindergarten_teacher").style is None
    teacher = personas.persona("kindergarten_teacher")
    for seed in range(1, 4):  # (a random theme is one of a family the persona favours more often)
        deck = _deck(None, int_seed=seed, theme="random", persona="kindergarten_teacher")
        expected = themes.pick(themes.RANDOM, random_util.Rng(seed).child("theme"), True, teacher.themes)
        assert deck.theme == expected.name


def test_personas_favour_image_looks_there_are_for_looks_slides_ask_for():
    asked = {
        look
        for value in vars(content_generators).values()
        if isinstance(value, ImageSlot)
        for look in (value.aesthetic, *value.backups)
    }
    for name, persona in personas.PERSONAS.items():
        assert persona.looks and set(persona.looks) <= asked, (name, set(persona.looks) - asked)
        for favourite in persona.looks.values():
            profiles.profile(favourite)  # (a ValueError for a look there isn't)


def test_a_talk_searches_its_persona_s_favourite_looks_first(schema, monkeypatch):
    seen = []
    for_talk = image_context.for_talk
    monkeypatch.setattr(image_context, "for_talk", lambda talk: seen.append(talk) or for_talk(talk))
    _deck(None, persona="medieval_historian")
    assert seen[-1].persona_looks == personas.persona("medieval_historian").looks
    assert seen[-1].tries("weird") == ("medieval", "weird")
    _deck(None, persona="none")
    assert seen[-1].persona_looks == {} and seen[-1].tries("weird") == ("weird",)


# THE PRESENTER'S NAME


def test_the_persona_says_how_the_presenter_goes_by(schema):
    model = FakeModel()
    _deck(model, persona="disgraced_professor")
    description = _spine(model)["presenter_name"]["description"]
    assert description.endswith(", with Prof. before the name, a title they still cling to (at most 40 characters)")
    assert "with a title such as Dr. or Prof. if it suits" not in description


def test_the_persona_s_name_styles_come_up_more_often():
    historian = personas.persona("medieval_historian")
    asked = collections.Counter(
        names.Naming.of(names.DEFAULT_STYLES, ["cats"], random_util.Rng(seed), True, historian.nudge).style
        for seed in range(200)
    )
    assert asked["famous_pun"] > 1.5 * max(asked["pun"], asked["fun_surname"])
    assert set(asked) == set(names.DEFAULT_STYLES)  # (the others come up too)
    # And so with talkgenerator's own names, in a classic talk (the pack has names in every style for cats)
    styles = collections.Counter(
        next(
            entry.style
            for entry in names.pack()
            if names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(seed), historian.nudge) in entry.names
        )
        for seed in range(200)
    )
    assert styles["famous_pun"] > 1.5 * max(styles["pun"], styles["fun_surname"])


def test_a_talk_that_says_which_name_styles_it_may_have_goes_by_those_alone(schema):
    styles = ",".join(names.DEFAULT_STYLES)
    model = FakeModel()
    _deck(model, int_seed=3, persona="disgraced_professor", name_styles=styles)
    description = _spine(model)["presenter_name"]["description"]
    assert "with a title such as Dr. or Prof. if it suits" in description and "Prof. before the name" not in description
    asked = names.Naming.of(names.DEFAULT_STYLES, ["cats"], random_util.Rng(3), True).request
    assert description == asked.description()  # (the style the dice pick without a nudge)

    classic = _deck(None, int_seed=2, persona="medieval_historian", name_styles=styles)
    assert classic.presenter == names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(2))
    nudged = _deck(None, int_seed=2, persona="medieval_historian")
    historian = personas.persona("medieval_historian")
    assert nudged.presenter == names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(2), historian.nudge)


def test_the_presenter_s_own_name_still_never_reaches_the_model(schema):
    model = FakeModel()
    deck = _deck(model, presenter="Ann Example", persona="kindergarten_teacher")
    request = model.requests[0]
    assert deck.presenter == "Ann Example"
    assert "presenter_name" not in json.dumps(request.json_schema)
    assert "Ann Example" not in request.system + json.dumps(request.model_dump())


# THE DECK, AND TALK.STARTED


@pytest.mark.parametrize("planned", [True, False], ids=["planned", "classic"])
@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_the_deck_and_talk_started_say_which_persona_the_talk_had(schema, planned, parallel):
    def model():
        return FakeModel() if planned else "none"

    events = list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", int_seed=5, llm=model(), parallel=parallel))
    started, finished = events[0], events[-1]
    assert isinstance(started, TalkStarted) and isinstance(finished, TalkFinished)
    persona = personas.pick(None, random_util.Rng(5))
    assert started.persona == finished.deck.persona
    assert (started.persona.name, started.persona.label, started.persona.voice) == (
        persona.name,
        persona.label,
        persona.voice,
    )
    if planned:
        assert started.persona.angle == persona.angle(random_util.Rng(5))
    else:
        assert started.persona.angle is None  # (a classic talk's persona has no angle: no model was told one)
    assert finished.deck.to_json() == _deck(model(), int_seed=5, parallel=parallel).to_json()
    assert Deck.from_json(finished.deck.to_json()).persona == finished.deck.persona
    assert json.loads(started.to_json())["persona"]["name"] == persona.name
    assert deck_metrics(finished.deck)["persona"] == persona.name  # (for talkgenerator check's reports)


def test_the_same_seed_and_answers_give_the_same_persona_and_talk(schema, tmp_path):
    cassette = tmp_path / "talk.json"
    recorded = _deck(llm.ReplayProvider(cassette, record=FakeModel()), int_seed=6)
    replayed = _deck(llm.ReplayProvider(cassette), int_seed=6)
    assert replayed.persona == recorded.persona is not None
    assert replayed.to_json() == recorded.to_json()
    assert {_deck(None, int_seed=seed).persona.name for seed in range(1, 9)} != {recorded.persona.name}


def test_a_talk_can_name_its_persona(schema):
    assert _deck(None, persona="kindergarten_teacher").persona.name == "kindergarten_teacher"
    assert _deck(None, persona="none").persona is None
    with pytest.raises(ValueError, match="There's no persona 'nope'"):
        _deck(None, persona="nope")
    with pytest.raises(ValueError, match="There's no persona 'nope'"):
        list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", persona="nope"))


def test_the_command_line_takes_a_persona(monkeypatch):
    parser = generator.get_argument_parser()
    args = parser.parse_args(["--topic", "cats", "--persona", "time_traveller", "--print_logs", "false"])
    assert args.persona == "time_traveller"
    assert parser.parse_args([]).persona is None
    with pytest.raises(SystemExit):
        parser.parse_args(["--persona", "nope"])

    given = {}
    monkeypatch.setattr(runtime_checker, "check_runtime_environment", lambda: True)
    monkeypatch.setattr(generator, "_generate_presentation", lambda **options: given.update(options))
    generator.generate_presentation_using_cli_arguments(args)
    assert given["persona"] == "time_traveller"
