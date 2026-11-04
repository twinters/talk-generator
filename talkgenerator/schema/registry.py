"""A small named registry, used for the slide generators and the presentation schemas.

Instead of star-importing modules to get at their generators, everything is registered under a
unique name (and optionally a group), and looked up explicitly:

    from talkgenerator.schema.slide_schemas import slide_generators
    from talkgenerator.schema.presentation_schema_types import schemas

    schemas.names()                      # ['default', 'interview', 'test', 'ted']
    slide_generators.get("Inspirobot")
    slide_generators.group("conclusion")
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, T] = {}
        self._groups: dict[str, list[str]] = {}

    def register(self, name: str, item: T, group: str | None = None) -> T:
        if not name:
            raise ValueError(f"Every {self._kind} needs a name")
        if name in self._items:
            raise ValueError(f"There already is a {self._kind} called {name!r}")
        self._items[name] = item
        if group is not None:
            self._groups.setdefault(group, []).append(name)
        return item

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"Unknown {self._kind} {name!r}; choose from: {', '.join(self._items)}") from None

    def group(self, group: str) -> list[T]:
        try:
            return [self._items[name] for name in self._groups[group]]
        except KeyError:
            raise KeyError(f"Unknown {self._kind} group {group!r}; choose from: {', '.join(self._groups)}") from None

    def groups(self, *groups: str) -> list[T]:
        """All items of the given groups, in that order."""
        return [item for group in groups for item in self.group(group)]

    def group_names(self) -> list[str]:
        return list(self._groups)

    def names(self) -> list[str]:
        return list(self._items)

    def __getitem__(self, name: str) -> T:
        return self.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __iter__(self) -> Iterator[T]:
        return iter(list(self._items.values()))

    def __len__(self) -> int:
        return len(self._items)
