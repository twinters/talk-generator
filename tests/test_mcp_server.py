"""Offline tests of the MCP server (`talkgenerator mcp`): its tools, called in-process the way an MCP client calls them,
with the fake schema, image sources and language model of test_plans and test_llm_talks, so nothing goes over the
network.

They need the MCP SDK (pip install 'talkgenerator[mcp]'), which the dev dependencies leave out on Windows on Arm (where
it doesn't install): there, run them in an x64 Python (see "Tests" in the README).
"""

import importlib.util
import json
import logging
import sys
import threading
import time
import warnings
from pathlib import Path

import anyio
import pytest

import talkgenerator
from talkgenerator import names, personas, run
from talkgenerator.llm import providers
from talkgenerator.models.deck import Deck
from talkgenerator.models.plan import TalkPlan
from talkgenerator.plan import external
from talkgenerator.plan.prompt import SPINE
from tests.test_llm_talks import FakeModel
from tests.test_llm_talks import images as images  # the fake image sources (an autouse fixture)
from tests.test_plans import CHART, STATEMENT, TWO_COLUMNS, _plan
from tests.test_plans import schema as schema  # the fake schema, with its own recipes as the defaults

needs_mcp = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None,
    reason="needs the MCP SDK (pip install 'talkgenerator[mcp]'; on Windows on Arm, in an x64 Python)",
)


@pytest.fixture
def server(tmp_path):
    from talkgenerator import mcp_server

    return mcp_server.make_server(tmp_path / "talks", progress_every=0.02)


def _calls(server, *calls, **options):
    """Call tools in one session, as (name, arguments) pairs, and return their results."""
    from mcp import Client

    async def call():
        async with Client(server, raise_exceptions=True) as client:
            return [await client.call_tool(name, arguments, **options) for name, arguments in calls]

    return anyio.run(call)


def _call(server, name, arguments=None, **options):
    (result,) = _calls(server, (name, arguments or {}), **options)
    return result


def _answer(result):
    """A tool's answer: its JSON, which the text the model reads is the same as."""
    assert not result.is_error, result.content[0].text
    assert json.loads(result.content[0].text) == result.structured_content
    return result.structured_content


def _error(result):
    assert result.is_error
    return result.content[0].text


def _inside(path, folder):
    return Path(path).resolve().is_relative_to(folder.resolve())


@pytest.fixture
def model_in_the_settings(monkeypatch):
    """A fake language model, which the settings name as the user's (with TALKGENERATOR_LLM)."""
    model = FakeModel()
    monkeypatch.setitem(providers._FACTORIES, "fake", lambda _: model)
    monkeypatch.setenv("TALKGENERATOR_LLM", "fake")
    return model


# THE TOOLS


@needs_mcp
def test_the_server_has_tools_to_look_things_up_and_to_make_talks(server):
    from mcp import Client

    async def list_tools():
        async with Client(server, raise_exceptions=True) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in anyio.run(list_tools)}
    assert set(tools) == {"list_formats", "describe_format", "get_plan_schema", "render_plan", "generate_talk"}
    for name in ("list_formats", "describe_format", "get_plan_schema"):
        assert tools[name].annotations.read_only_hint
    for name in ("render_plan", "generate_talk"):
        assert not tools[name].annotations.read_only_hint and not tools[name].annotations.destructive_hint
    # The language model comes from the user's settings, never from a tool call (so a model can't pick a paid one)
    assert set(tools["generate_talk"].input_schema["properties"]) == {
        "topic",
        "topic_or_title",
        "slides",
        "format",
        "language",
        "theme",
        "title",
        "presenter",
        "name_styles",
        "seed",
        "license_policy",
        "persona",
    }
    # A plan's JSON Schema is in render_plan's input too, so a client knows it without asking
    assert "SlidePlan" in json.dumps(tools["render_plan"].input_schema)


@needs_mcp
def test_the_formats_themes_and_languages_are_listed(server):
    listed = _answer(_call(server, "list_formats"))
    formats = {entry["format"]: entry["description"] for entry in listed["formats"]}
    assert formats["ted"] == external.FORMATS["ted"]
    assert {"classic", "random", "vintage paper", "chaos"} <= {theme["name"] for theme in listed["themes"]}
    assert all(theme["description"] for theme in listed["themes"])  # (for a menu)
    assert {"code": "nl", "name": "Dutch"} in listed["languages"]
    assert {"code": "sv", "name": "Swedish"} in listed["languages"]
    assert listed["name_styles"] == names.catalog()
    assert listed["personas"] == personas.catalog()
    policies = {entry["format"]: entry["license_policy"] for entry in listed["formats"]}
    assert (policies["ted"], policies["default"]) == ("open", "all")
    assert {"all", "open", "public-domain"} <= {policy["name"] for policy in listed["license_policies"]}
    looks = {look["name"]: look["kind"] for look in listed["image_looks"]}
    assert (looks["vintage"], looks["cursed"]) == ("look", "flavour pack")


@needs_mcp
def test_a_formats_slides_are_its_catalog(server):
    assert _answer(_call(server, "describe_format", {"format": "ted"})) == external.catalog("ted")
    assert _answer(_call(server, "describe_format"))["format"] == "default"
    assert "there's no format 'karaoke'; the formats are default" in _error(
        _call(server, "describe_format", {"format": "karaoke"})
    )


@needs_mcp
def test_the_plan_schema_is_the_plans_json_schema(server):
    assert _answer(_call(server, "get_plan_schema")) == TalkPlan.model_json_schema()


# RENDERING A PLAN


@needs_mcp
def test_a_plan_is_rendered_in_the_output_folder(schema, server, tmp_path):
    plan = _plan(TWO_COLUMNS, STATEMENT, CHART, theme="vintage paper")
    report = _answer(_call(server, "render_plan", {"plan": plan.model_dump(mode="json"), "presenter": "Ann Example"}))

    assert report["summary"]["as_planned"] == 3
    assert report["presenter"] == "Ann Example"
    assert report["theme"].startswith("vintage paper")  # the plan's own theme
    for key in ("pptx", "deck_json", "contact_sheet"):
        assert Path(report[key]).is_file() and _inside(report[key], tmp_path / "talks"), key
    assert _deck(report).title == "The Secret Life of Cats"
    # With the report's seed, the same plan renders as the same deck again (in a file of its own)
    again = _answer(_call(server, "render_plan", {"plan": plan.model_dump(mode="json"), "seed": report["seed"]}))
    assert again["pptx"] != report["pptx"]
    assert again["slides"] == report["slides"]


@needs_mcp
def test_a_plan_the_model_sends_as_text_works_too(schema, server):
    # Some clients send objects as JSON text (Claude Desktop is known to)
    report = _answer(_call(server, "render_plan", {"plan": _plan(CHART).model_dump_json()}))
    assert report["summary"]["as_planned"] == 1


@needs_mcp
def test_a_plan_that_cant_be_rendered_says_why(schema, server):
    assert "there's no theme 'glitter'" in _error(
        _call(server, "render_plan", {"plan": _plan(CHART, theme="glitter").model_dump(mode="json")})
    )
    assert "there's no format 'karaoke'" in _error(
        _call(server, "render_plan", {"plan": _plan(CHART, format="karaoke").model_dump(mode="json")})
    )
    assert "there's no language 'xx'" in _error(
        _call(server, "render_plan", {"plan": _plan(CHART, language="xx").model_dump(mode="json")})
    )
    problem = _error(_call(server, "render_plan", {"plan": {"topic": "cats", "slides": []}}))
    assert "plan.title" in problem and "Field required" in problem


@needs_mcp
def test_nothing_is_saved_outside_the_output_folder(schema, server, tmp_path, model_in_the_settings):
    plan = _plan(CHART).model_copy(update={"title": "../../../Escape/..\\..\\again"})
    rendered = _answer(_call(server, "render_plan", {"plan": plan.model_dump(mode="json")}))
    made = _answer(_call(server, "generate_talk", {"topic": "../../../escape", "slides": 3}))
    for report in (rendered, made):
        for key in ("pptx", "deck_json", "contact_sheet"):
            assert report[key] is None or _inside(report[key], tmp_path / "talks"), report[key]
    assert {path.name for path in tmp_path.iterdir()} <= {"talks", "config"}


# MAKING A TALK ON A TOPIC


@needs_mcp
def test_the_language_model_of_the_settings_writes_the_talk(schema, server, tmp_path, model_in_the_settings):
    report = _answer(
        _call(server, "generate_talk", {"topic": "cats", "slides": 5, "theme": "neon", "presenter": "Ann Example"})
    )

    assert len(model_in_the_settings.requests) == 1
    assert report["language_model"] == "fake:model"
    assert report["summary"] == {"deck_slides": 5, "written_by_language_model": 5}
    assert (report["title"], report["presenter"], report["topics"]) == ("The title", "Ann Example", ["cats"])
    assert report["theme"].startswith("neon")
    assert report["usage"]["requests"] == 1
    assert report["checks"] == []
    assert "notes" not in report
    for key in ("pptx", "deck_json", "contact_sheet"):
        assert Path(report[key]).is_file() and _inside(report[key], tmp_path / "talks"), key
    deck = _deck(report)
    assert (deck.seed, len(deck.slides)) == (report["seed"], 5)


def _deck(report):
    return Deck.from_json(Path(report["deck_json"]).read_text(encoding="utf-8"))


@needs_mcp
def test_a_talk_keeps_to_the_license_policy_it_asks_for(schema, server, model_in_the_settings):
    report = _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 3, "license_policy": "open"}))
    assert report["license_policy"] == _deck(report).license_policy == "open"
    assert _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 3}))["license_policy"] == "all"


@needs_mcp
def test_the_model_names_the_presenter_in_a_style_the_talk_asks_for(schema, server, model_in_the_settings):
    model_in_the_settings.change = lambda answer: answer[SPINE].update(presenter_name="Prof. Clawdette Purrkins")
    report = _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4, "name_styles": ["famous_pun"]}))
    assert report["presenter"] == _deck(report).presenter == "Prof. Clawdette Purrkins"
    (request,) = model_in_the_settings.requests
    description = request.json_schema["properties"][SPINE]["properties"]["presenter_name"]["description"]
    assert description.startswith(names.STYLES["famous_pun"].asked)


@needs_mcp
def test_a_talk_has_the_persona_it_asks_for(schema, server, model_in_the_settings):
    report = _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4, "persona": "time_traveller"}))
    assert report["persona"]["name"] == _deck(report).persona.name == "time_traveller"
    (request,) = model_in_the_settings.requests
    assert "The presenter: a time traveller trying not to give too much away" in request.messages[0].content
    assert "persona" not in _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4, "persona": "none"}))


@needs_mcp
def test_a_talk_can_be_made_again_with_its_seed(schema, server, model_in_the_settings):
    talk = {"topic": "cats", "slides": 4, "presenter": "Ann Example"}
    first, other, again = (
        _answer(result)
        for result in _calls(server, ("generate_talk", talk), ("generate_talk", talk), ("generate_talk", talk))
    )
    repeated = _answer(_call(server, "generate_talk", {**talk, "seed": first["seed"]}))
    assert len({first["pptx"], other["pptx"], again["pptx"], repeated["pptx"]}) == 4  # every talk in a file of its own
    assert repeated["seed"] == first["seed"]
    assert _deck(repeated).slides == _deck(first).slides


@needs_mcp
def test_without_a_language_model_the_talk_is_classic_and_english(schema, server):
    report = _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4, "language": "nl"}))
    assert report["language_model"] is None
    assert report["summary"]["written_by_language_model"] == 0
    assert report["language"] == "en"
    assert report["notes"] == [
        "talks in other languages than English need slides a language model wrote, and this one has none, so it's in "
        "English (the settings name no language model)"
    ]


@needs_mcp
def test_the_tools_make_talks_without_deprecation_warnings(schema, server):
    """The server makes its talks as the command line does, not with the deprecated generate_presentation (see
    test_deprecations), so a client sees no DeprecationWarning of talkgenerator's on the server's stderr."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4}))
        _answer(_call(server, "render_plan", {"plan": _plan(CHART).model_dump(mode="json")}))
    assert [
        str(caught_warning.message)
        for caught_warning in caught
        if "throughout talkgenerator 5" in str(caught_warning.message)
    ] == []


@needs_mcp
def test_a_talk_on_what_the_user_asked_for_says_how_it_was_read(schema, server):
    typed = "Why I joined a penguin cult"
    report = _answer(_call(server, "generate_talk", {"topic_or_title": typed, "slides": 4}))
    assert report["topic_or_title"] == {"text": typed, "read_as": "title"}  # (no language model: the guess)
    assert (report["title"], report["topics"]) == (typed, ["penguin"])
    assert _deck(report).topic_or_title.read_as == "title"
    assert "topic_or_title" not in _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4}))


@needs_mcp
def test_a_topic_or_title_goes_without_a_topic_and_a_title(schema, server):
    for given in ({"topic": "cats"}, {"title": "Cats!"}):
        problem = _error(_call(server, "generate_talk", {"topic_or_title": "penguins", **given}))
        assert "give topic_or_title instead of a topic and a title" in problem
    assert "give a topic, a title or a topic_or_title" in _error(_call(server, "generate_talk", {"slides": 4}))
    assert "at least 1 character" in _error(_call(server, "generate_talk", {"topic_or_title": ""}))


@needs_mcp
def test_a_talk_the_model_doesnt_write_says_so(schema, server, monkeypatch):
    from talkgenerator import llm

    monkeypatch.setitem(providers._FACTORIES, "fake", lambda _: FakeModel(fail=llm.RateLimited("free quota used up")))
    monkeypatch.setenv("TALKGENERATOR_LLM", "fake")
    report = _answer(_call(server, "generate_talk", {"topic": "cats", "slides": 4, "language": "nl"}))
    assert report["language_model"] == "fake:model"
    assert report["usage"]["failed_requests"] == 1
    assert report["notes"] == [
        "the language model wrote none of the slides, so the talk is classic (the server's log says why)",
        "talks in other languages than English need slides a language model wrote, and this one has none, so it's in "
        "English",
    ]


@needs_mcp
def test_what_a_talk_cant_be_is_refused(schema, server, monkeypatch):
    assert "there's no theme 'glitter'" in _error(_call(server, "generate_talk", {"topic": "cats", "theme": "glitter"}))
    assert "there's no format 'karaoke'" in _error(
        _call(server, "generate_talk", {"topic": "cats", "format": "karaoke"})
    )
    assert "there's no language 'xx'" in _error(_call(server, "generate_talk", {"topic": "cats", "language": "xx"}))
    assert "there's no name style 'custom'" in _error(
        _call(server, "generate_talk", {"topic": "cats", "name_styles": ["pun", "custom"]})
    )
    assert "there's no persona 'pirate'" in _error(
        _call(server, "generate_talk", {"topic": "cats", "persona": "pirate"})
    )
    assert "less than or equal to 40" in _error(_call(server, "generate_talk", {"topic": "cats", "slides": 400}))
    assert "no license policy 'copyleft'" in _error(
        _call(server, "generate_talk", {"topic": "cats", "license_policy": "copyleft"})
    )
    assert "at least 1 character" in _error(_call(server, "generate_talk", {"topic": ""}))
    monkeypatch.setenv("TALKGENERATOR_LLM", "no-such-provider")
    assert "the language model the settings ask for can't be used" in _error(
        _call(server, "generate_talk", {"topic": "cats"})
    )


# KEYS, PROGRESS, ONE TALK AT A TIME


SECRETS = {
    "OPENROUTER_API_KEY": "sk-or-v1-secret-openrouter-key",
    "ANTHROPIC_API_KEY": "sk-ant-secret-anthropic-key",
    "OPENAI_API_KEY": "sk-secret-openai-key",
    "UNSPLASH_ACCESS_KEY": "secret-unsplash-key",
    "PIXABAY_KEY": "secret-pixabay-key",
    "PEXELS_KEY": "secret-pexels-key",
    "GIPHY_API_KEY": "secret-giphy-key",
    "REDDIT_CLIENT_ID": "secret-reddit-id",
    "REDDIT_CLIENT_SECRET": "secret-reddit-secret",
    "OPENVERSE_CLIENT_SECRET": "secret-openverse-secret",
}


@needs_mcp
def test_keys_never_show_up_in_what_the_tools_say_or_log(schema, server, monkeypatch, caplog, model_in_the_settings):
    for name, value in SECRETS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("REDDIT_USER_AGENT", "talkgenerator tests")
    monkeypatch.setattr(logging.getLogger("talkgenerator"), "propagate", True)  # (to caplog, at the root)
    caplog.set_level(logging.DEBUG)

    results = _calls(
        server,
        ("list_formats", {}),
        ("describe_format", {"format": "default"}),
        ("get_plan_schema", {}),
        ("render_plan", {"plan": _plan(TWO_COLUMNS, STATEMENT, CHART).model_dump(mode="json")}),
        ("render_plan", {"plan": _plan(CHART, theme="glitter").model_dump(mode="json")}),
        ("generate_talk", {"topic": "cats", "slides": 4}),
        ("generate_talk", {"topic": "cats", "language": "xx"}),
    )

    said = [block.text for result in results for block in result.content]
    said += [json.dumps(result.structured_content) for result in results]
    assert _answer(results[5])["sources_without_keys"] == []  # the keys were there
    for value in SECRETS.values():
        assert not any(value in text for text in said)
        assert value not in caplog.text


@needs_mcp
def test_a_client_hears_that_a_talk_is_still_being_made(schema, server, monkeypatch):
    def slow_render(plan, **options):
        time.sleep(0.3)
        return {"title": plan.title}

    monkeypatch.setattr(external, "render_plan", slow_render)
    progress = []

    async def heard(value, total, message):
        progress.append((value, message))

    report = _answer(
        _call(server, "render_plan", {"plan": _plan(CHART).model_dump(mode="json")}, progress_callback=heard)
    )
    assert report == {"title": "The Secret Life of Cats"}
    assert len(progress) >= 3
    assert [value for value, _ in progress] == sorted({value for value, _ in progress})  # always more
    assert all(message.startswith("Rendering the plan: ") for _, message in progress)


@needs_mcp
def test_talks_are_made_one_at_a_time(schema, server, monkeypatch):
    lock, busy, most = threading.Lock(), [0], [0]

    def slow_render(plan, **options):
        with lock:
            busy[0] += 1
            most[0] = max(most[0], busy[0])
        time.sleep(0.2)
        with lock:
            busy[0] -= 1
        return {"title": plan.title}

    monkeypatch.setattr(external, "render_plan", slow_render)
    from mcp import Client

    async def at_once():
        results = []
        async with Client(server, raise_exceptions=True) as client:

            async def call(name, arguments, after=0.0):
                await anyio.sleep(after)
                results.append((name, await client.call_tool(name, arguments)))

            async with anyio.create_task_group() as group:
                group.start_soon(call, "render_plan", {"plan": _plan(CHART).model_dump(mode="json")})
                group.start_soon(call, "render_plan", {"plan": _plan(STATEMENT).model_dump(mode="json")})
                group.start_soon(call, "list_formats", {}, 0.05)
        return results

    results = anyio.run(at_once)
    assert [name for name, _ in results] == ["list_formats", "render_plan", "render_plan"]
    assert all(not result.is_error for _, result in results)
    assert most[0] == 1


@needs_mcp
def test_a_folder_that_cant_be_written_to_is_an_error_the_model_reads(schema, server, monkeypatch):
    def no_room(plan, **options):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(external, "render_plan", no_room)
    problem = _error(_call(server, "render_plan", {"plan": _plan(CHART).model_dump(mode="json")}))
    assert "couldn't save the talk in" in problem and "Permission denied" in problem


# THE COMMAND


@needs_mcp
def test_talkgenerator_mcp_serves_the_tools_over_stdio(tmp_path):
    from mcp import Client, StdioServerParameters

    # A server of its own, as a client starts it: nothing it logs may get in the way of the protocol on stdout
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "talkgenerator.run", "mcp", "--output_folder", str(tmp_path / "talks")],
        env={"DISABLE_CACHE": "1", "TALKGENERATOR_CONFIG_DIR": str(tmp_path / "config")},
        cwd=tmp_path,
    )

    async def ask():
        async with Client(parameters) as client:
            tools = await client.list_tools()
            return tools, await client.call_tool("list_formats", {})

    tools, formats = anyio.run(ask)
    assert "render_plan" in {tool.name for tool in tools.tools}
    assert "ted" in {entry["format"] for entry in _answer(formats)["formats"]}


@needs_mcp
def test_the_output_folder_is_the_users_documents_unless_given(tmp_path):
    from talkgenerator import mcp_server

    assert mcp_server.output_folder_of(None) == mcp_server.default_output_folder().resolve()
    assert mcp_server.default_output_folder().name == "talkgenerator"
    assert mcp_server.output_folder_of(str(tmp_path / "talks")) == (tmp_path / "talks").resolve()


def test_without_the_mcp_sdk_the_command_says_how_to_install_it(monkeypatch, capsys):
    # As if the SDK weren't installed: importing it (or any of its modules imported before) fails
    for name in [name for name in sys.modules if name == "mcp" or name.startswith("mcp.")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.delitem(sys.modules, "talkgenerator.mcp_server", raising=False)
    monkeypatch.delattr(talkgenerator, "mcp_server", raising=False)
    assert run._mcp_server() is None

    monkeypatch.setattr(run, "_mcp_server", lambda: None)
    assert run._mcp(["--output_folder", "talks"]) == 2
    assert "pip install 'talkgenerator[mcp]'" in capsys.readouterr().err
