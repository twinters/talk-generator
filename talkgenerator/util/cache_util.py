# from https://stackoverflow.com/questions/1151658/python-hashable-dicts
from typing import Any


class HashableDict(dict):
    """A hashable version of a dictionary, useful for when a function needs to be cached but uses a dict as an
    argument"""

    def __key(self) -> tuple[tuple[Any, Any], ...]:
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(self.__key())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HashableDict) and self.__key() == other.__key()
