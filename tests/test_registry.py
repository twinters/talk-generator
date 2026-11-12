import pytest

from talkgenerator import generator
from talkgenerator.schema.presentation_schema_types import get_schema, schemas
from talkgenerator.schema.registry import Registry
from talkgenerator.schema.slide_schemas import slide_generators


def test_registry_lookup_and_groups():
    registry: Registry[int] = Registry("number")
    registry.register("one", 1, group="odd")
    registry.register("two", 2, group="even")
    registry.register("three", 3, group="odd")
    assert registry.get("two") == registry["two"] == 2
    assert registry.group("odd") == [1, 3]
    assert registry.groups("even", "odd") == [2, 1, 3]
    assert registry.names() == ["one", "two", "three"]
    assert "one" in registry and len(registry) == 3


def test_registry_refuses_duplicates_and_explains_unknown_names():
    registry: Registry[int] = Registry("number")
    registry.register("one", 1)
    with pytest.raises(ValueError, match="already"):
        registry.register("one", 1)
    with pytest.raises(KeyError, match="choose from: one"):
        registry.get("two")


def test_schemas_are_registered():
    assert schemas.names() == [
        "default",
        "interview",
        "test",
        "ted",
        "pitch",
        "academic",
        "corporate",
        "keynote",
        # (D79)
        "infomercial",
        "documentary",
    ]
    assert get_schema("ted") is schemas.get("ted")


def test_every_schema_only_uses_registered_slide_generators():
    registered = set(map(id, slide_generators))
    for name in schemas.names():
        assert schemas.get(name).slide_generators, name
        # (or a chart's or a diagram's copy that tries a picture first, whose text version is the registered one: D73)
        assert all(
            id(generator) in registered or id(generator.text_version) in registered
            for generator in schemas.get(name).slide_generators
        ), name


def test_listing():
    overview = generator.describe_schemas()
    assert "ted (" in overview and "Inspirobot" in overview
