"""Offline tests of talks' personas (talkgenerator.personas): who presents a talk, as its dice pick them (or as it
names them, or among the ones it allows), and how they shape it, with a language model or without: its kinds of
slides, its title, its presenter's name, the model's voice and angle, and the format when the talk leaves it to its
seed (D61). The deck and talk.started say which persona a talk had.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images (a talk with
schema random gets the fake schema too, whichever format its seed picks, and its deck names that format).
"""

import collections
import dataclasses
import json
import statistics

import pytest

from talkgenerator import generator, llm, names, personas, runtime_checker
from talkgenerator.checks import benchmark
from talkgenerator.checks.deck import deck_metrics
from talkgenerator.design import themes
from talkgenerator.images import context as image_context
from talkgenerator.images import profiles
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import Deck, TalkPersona
from talkgenerator.models.events import TalkFinished, TalkStarted
from talkgenerator.plan.prompt import SPINE
from talkgenerator.schema import content_generators, slide_schemas
from talkgenerator.schema import presentation_schema_types as schema_types
from talkgenerator.schema.formats import pitch
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


def _deck(model, int_seed=1, topic="cats", schema_name="fake", **options):
    """A talk of the fake schema (whatever format a talk with schema random gets), as a deck that names its format."""
    _, slide_deck, _ = generator._generate_presentation(
        schema=schema_name, slides=NUM_SLIDES, topic=topic, int_seed=int_seed, save_ppt=False, llm=model, **options
    )
    return slide_deck.to_deck()


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
    assert not any(personas.PAST in entry["description"] for entry in personas.catalog())
    assert personas.choices() == ("random", "none", *personas.PERSONAS)


def test_a_retiree_s_old_job_is_one_the_talk_s_dice_pick():
    # (a retired lighthouse keeper's talks were all about the lighthouse: the user, 2026-11-09, "why not retired person?")
    retiree = personas.PERSONAS["retiree"]
    lived = [personas.pick("retiree", random_util.Rng(seed)) for seed in range(200)]
    assert lived == [
        personas.pick("retiree", random_util.Rng(seed)) for seed in range(200)
    ]  # (the same seed, the same)
    pasts = collections.Counter(next(past for past in retiree.pasts if past in each.voice) for each in lived)
    assert set(pasts) == set(retiree.pasts)
    assert min(pasts.values()) > len(lived) / len(retiree.pasts) / 3  # (none of them rare: about 12 each of 200)
    for each in lived:
        (past,) = [past for past in retiree.pasts if past in each.voice]
        assert past in each.job_hint and personas.PAST not in each.voice + each.job_hint + "".join(each.angles)
        assert any(past in angle for angle in each.angles) and not all(past in angle for angle in each.angles)
    # (picked at random as well, with the stream of its own: the other personas are the same objects as before)
    drawn = [personas.pick(None, random_util.Rng(seed)) for seed in range(300)]
    assert any(each.name == "retiree" and personas.PAST not in each.voice for each in drawn)
    assert all(each is personas.PERSONAS[each.name] for each in drawn if each.name != "retiree")


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
    # (over 300 talks: a funnel comes up in about one talk in seventeen, so 150 left its share to chance)
    seeds = range(300)
    historian = _picked_tags(personas.persona("medieval_historian"), seeds)
    founder = _picked_tags(personas.persona("startup_founder"), seeds)
    teacher = _picked_tags(personas.persona("kindergarten_teacher"), seeds)
    plain = _picked_tags(None, seeds)
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
        == f"a title of your own for the talk, {founder.title_hint}, in English (at most 80 characters)"
    )
    assert f"- title: a title of your own for the talk, {founder.title_hint}, in English" in _prompt(model)

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
    assert (
        _spine(model)["title"]["description"] == "a title of your own for the talk, in English (at most 80 characters)"
    )
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


@pytest.mark.slow
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


# THE PERSONAS A TALK ALLOWS (decision D61)


def _picks(seeds=range(400), weights=None, among=None):
    return [personas.pick(None, random_util.Rng(seed), weights, among).name for seed in seeds]


def test_a_talk_says_which_personas_its_seed_picks_from():
    assert personas.allowed(None) == tuple(personas.PERSONAS)
    # In the order of PERSONAS, whatever order and case they come in, as a list or separated by commas
    assert personas.allowed(" Consultant,startup_founder ") == ("startup_founder", "consultant")
    assert personas.allowed(["consultant", "startup_founder", "consultant"]) == ("startup_founder", "consultant")
    with pytest.raises(ValueError, match="There's no persona 'pirate'; there are disgraced_professor, startup_founder"):
        personas.allowed("consultant,pirate")
    for alone in ("random", "none"):
        with pytest.raises(ValueError, match=f"'{alone}' goes alone, as persona"):
            personas.allowed(["consultant", alone])
    for nothing in ("", " , ", []):
        with pytest.raises(ValueError, match="at least one persona"):
            personas.allowed(nothing)


def test_the_seed_picks_only_among_the_personas_a_talk_allows():
    two = ("startup_founder", "retiree")
    picked = collections.Counter(_picks(among=two))
    assert set(picked) == set(two) and min(picked.values()) > 150  # (each about as often: 200 of 400)
    assert set(_picks(among=["time_traveller"])) == {"time_traveller"}
    # By a format's weights too, among the allowed: a startup founder pitches more often than a retiree
    pitches = collections.Counter(_picks(weights=pitch.PITCH.personas, among=two))
    assert pitches["startup_founder"] > 3 * pitches["retiree"] > 0
    # Allowing all of them is allowing any: the same persona as before there was a choice of them
    assert _picks() == _picks(among=personas.PERSONAS) == _picks(among=",".join(personas.PERSONAS))
    assert _picks(weights=pitch.PITCH.personas) == _picks(weights=pitch.PITCH.personas, among=personas.PERSONAS)


def test_a_talk_whose_persona_is_allowed_keeps_it_whichever_others_are_left_out():
    every = _picks()
    without = [name for name in personas.PERSONAS if name not in ("startup_founder", "influencer")]
    fewer = _picks(among=without)
    for before, after in zip(every, fewer, strict=True):
        assert after == before if before in without else after in without
    # And the others' talks are shared out among the allowed ones as their weights say (each as likely, here)
    moved = collections.Counter(after for before, after in zip(every, fewer, strict=True) if before not in without)
    assert len(moved) >= 6


def test_a_persona_the_talk_names_goes_before_the_ones_it_allows():
    # (as a presenter's name goes before the name styles)
    assert personas.pick("consultant", random_util.Rng(1), among=["startup_founder"]).name == "consultant"
    assert personas.pick("none", random_util.Rng(1), among=["startup_founder"]) is None


def test_a_talk_s_persona_is_one_it_allows(schema):
    allowed = ("medieval_historian", "kindergarten_teacher")
    for seed in range(1, 7):
        deck = _deck(None, int_seed=seed, personas=allowed)
        assert deck.persona.name in allowed
        assert deck.persona.name == personas.pick(None, random_util.Rng(seed), among=allowed).name
    # The same seed and personas, the same talk; and in a stream
    assert _deck(None, int_seed=3, personas=allowed).to_json() == _deck(None, int_seed=3, personas=allowed).to_json()
    events = list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", int_seed=3, llm="none", personas=allowed))
    assert (
        events[0].persona.name == events[-1].deck.persona.name == _deck(None, int_seed=3, personas=allowed).persona.name
    )
    with pytest.raises(ValueError, match="There's no persona 'pirate'"):
        _deck(None, personas="pirate")


def test_the_command_line_takes_the_personas_the_seed_picks_from(monkeypatch):
    parser = generator.get_argument_parser()
    args = parser.parse_args(["--topic", "cats", "--personas", "consultant,startup_founder", "--print_logs", "false"])
    assert args.personas == ("startup_founder", "consultant")
    assert parser.parse_args([]).personas is None
    for wrong in ("nope", "consultant,none", ""):
        with pytest.raises(SystemExit):
            parser.parse_args(["--personas", wrong])

    given = {}
    monkeypatch.setattr(runtime_checker, "check_runtime_environment", lambda: True)
    monkeypatch.setattr(generator, "_generate_presentation", lambda **options: given.update(options))
    generator.generate_presentation_using_cli_arguments(args)
    assert given["personas"] == ("startup_founder", "consultant")


# THE FORMAT, WHEN A TALK LEAVES IT TO ITS SEED (decision D61)


FAVOURITES = {
    "startup_founder": "pitch",
    "disgraced_professor": "academic",
    "consultant": "corporate",
    "motivational_speaker": "keynote",
}


def test_personas_favour_formats_a_talk_s_seed_can_pick():
    assert set(schema_types.FORMAT_WEIGHTS) <= set(schema_types.schemas.names())
    # The formats meant for talks: not ted (the TED-like talk's copyright-free images are a license policy), interview
    # or test
    assert not {"ted", "interview", "test"} & set(schema_types.FORMAT_WEIGHTS)
    assert schema_types.choices() == ("random", *schema_types.schemas.names())
    for name, persona in personas.PERSONAS.items():
        assert persona.formats and set(persona.formats) <= set(schema_types.FORMAT_WEIGHTS), name
        assert all(0.2 <= factor <= 15 for factor in persona.formats.values()), name


def test_most_talks_are_ted_like_and_a_specialist_s_favourite_format_comes_next():
    # (decision D63: the user asked for more TED-like talks after reviewing 35, so with every persona most talks are
    # TED-like, and a specialist's favourite format comes second, in about two of their talks in five)
    for name, persona in personas.PERSONAS.items():
        odds = schema_types.format_odds(persona)
        assert sum(odds.values()) == pytest.approx(1)
        assert max(odds, key=odds.__getitem__) == "default" and odds["default"] >= 0.45, (name, odds)
        favourite = FAVOURITES.get(name)
        if favourite is not None:
            rest = [share for format_name, share in odds.items() if format_name not in ("default", favourite)]
            assert 0.3 <= odds[favourite] <= 0.45 and odds[favourite] > 3 * max(rest), (name, odds)
            # (and far more often than with any other persona)
            others = [
                schema_types.format_odds(other)[favourite] for other in personas.PERSONAS.values() if other != persona
            ]
            assert odds[favourite] > 3 * max(others), (name, favourite)
        assert min(odds.values()) > 0.02, (name, odds)  # (and every format keeps some chance)
    # Without a persona, 8 talks in 10 are TED-like
    assert schema_types.format_odds(None)["default"] >= 0.75


def test_the_seed_picks_a_format_as_often_as_the_persona_s_odds_say():
    for name in ("startup_founder", "disgraced_professor", "passionate_expert", "kindergarten_teacher"):
        persona = personas.persona(name)
        picked = collections.Counter(
            schema_types.pick_format("random", random_util.Rng(seed), persona) for seed in range(2000)
        )
        assert set(picked) == set(schema_types.FORMAT_WEIGHTS), name  # (all of them come up)
        for format_name, odds in schema_types.format_odds(persona).items():
            assert picked[format_name] / 2000 == pytest.approx(odds, abs=0.04), (name, format_name)


def test_across_the_personas_most_talks_are_ted_like_and_pitches_and_academic_talks_the_rarest():
    shares = {
        name: statistics.mean(schema_types.format_odds(persona)[name] for persona in personas.PERSONAS.values())
        for name in schema_types.FORMAT_WEIGHTS
    }
    assert shares["default"] >= 0.69  # (7 talks in 10: D63)
    assert all(0.04 < share < 0.12 for name, share in shares.items() if name != "default"), shares
    # (the user found pitches and academic talks the most boring: they're rarer than all-hands and keynotes)
    assert max(shares["pitch"], shares["academic"]) < min(shares["corporate"], shares["keynote"]), shares


def test_a_format_the_talk_names_is_its_format():
    founder = personas.persona("startup_founder")
    for seed in range(30):
        assert schema_types.pick_format("academic", random_util.Rng(seed), founder) == "academic"
        assert schema_types.pick_format("ted", random_util.Rng(seed), founder) == "ted"


def test_the_same_seed_picks_the_same_persona_and_format_and_the_format_moves_nothing_else():
    def picked(seed):
        rng = random_util.Rng(seed)
        persona = personas.pick(None, rng)
        return persona.name, schema_types.pick_format("random", rng, persona)

    assert [picked(seed) for seed in range(200)] == [picked(seed) for seed in range(200)]
    assert len({format_name for _, format_name in map(picked, range(200))}) == len(schema_types.FORMAT_WEIGHTS)
    # The format comes from a stream of its own: the persona and the theme are what they were before it was picked
    for seed in range(20):
        rng = random_util.Rng(seed)
        schema_types.pick_format("random", rng, personas.pick(None, rng))
        assert personas.pick(None, rng) == personas.pick(None, random_util.Rng(seed))
        assert themes.pick("random", rng.child("theme"), True) == themes.pick(
            "random", random_util.Rng(seed).child("theme"), True
        )


def test_a_talk_that_leaves_its_format_to_its_seed_has_the_one_its_persona_favours(schema):
    seen = set()
    for seed in range(1, 9):
        deck = _deck(None, int_seed=seed, schema_name="random")
        persona = personas.pick(None, random_util.Rng(seed))
        assert deck.persona.name == persona.name  # (the persona first, as a TED-like talk's)
        assert deck.schema_name == schema_types.pick_format("random", random_util.Rng(seed), persona)
        seen.add(deck.schema_name)
    assert "default" in seen
    # The persona it names, and the personas it allows, weigh in on the format
    founders = {
        _deck(None, int_seed=seed, schema_name="random", persona="startup_founder").schema_name for seed in range(1, 9)
    }
    assert "pitch" in founders
    professor = _deck(None, int_seed=2, schema_name="random", personas=["disgraced_professor"])
    expected = schema_types.pick_format("random", random_util.Rng(2), personas.persona("disgraced_professor"))
    assert professor.persona.name == "disgraced_professor" and professor.schema_name == expected
    # The deck and the stream say which format the talk got, and the same seed gives the same talk
    events = list(generator.stream_talk("random", NUM_SLIDES, topic="cats", int_seed=4, llm="none"))
    assert isinstance(events[-1], TalkFinished)
    assert events[-1].deck.schema_name == _deck(None, int_seed=4, schema_name="random").schema_name
    assert events[-1].deck.to_json() == _deck(None, int_seed=4, schema_name="random").to_json()
    assert deck_metrics(events[-1].deck)["format"] == events[-1].deck.schema_name  # (for talkgenerator check)


def test_a_talk_without_a_persona_gets_a_format_by_the_formats_own_weights(schema):
    for seed in range(1, 6):
        deck = _deck(None, int_seed=seed, schema_name="random", persona="none")
        assert deck.persona is None
        assert deck.schema_name == schema_types.pick_format("random", random_util.Rng(seed), None)


def test_a_talk_s_license_policy_holds_whatever_format_its_seed_picks(schema):
    for seed in range(1, 5):
        assert _deck(None, int_seed=seed, schema_name="random", license_policy="open").license_policy == "open"


def test_the_command_line_leaves_the_format_to_the_seed_with_random():
    parser = generator.get_argument_parser()
    assert parser.parse_args(["--schema", "random"]).schema == "random"
    assert parser.parse_args([]).schema == "default"
    with pytest.raises(SystemExit):
        parser.parse_args(["--schema", "karaoke"])


def test_the_check_reports_the_formats_and_personas_its_talks_got(schema):
    report = benchmark.run(
        ["cats"], [1, 2, 3], schema="random", slides=NUM_SLIDES, determinism=False, personas="consultant,influencer"
    )
    assert report["summary"]["formats"] == dict(
        sorted(collections.Counter(talk["metrics"]["format"] for talk in report["talks"]).items())
    )
    assert set(report["summary"]["personas"]) <= {"consultant", "influencer"}
    assert sum(report["summary"]["personas"].values()) == 3
    assert report["license_policy"] == "each format's" and report["personas"] == "consultant,influencer"
