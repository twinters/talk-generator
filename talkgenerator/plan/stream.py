"""Reading a JSON object while a language model writes it, one property at a time.

A talk's plan comes back as one JSON object whose properties are its slides, in order. ObjectReader hands over each
top-level property as soon as its value is complete, so slide 2 can be prepared while the model writes slide 3. Text
before the object (a Markdown fence, a word of introduction) is skipped, and a property whose value doesn't parse is
left out: that slide falls back to the classic generator.
"""

from __future__ import annotations

import json
from typing import Any


class ObjectReader:
    def __init__(self) -> None:
        self._text = ""
        self._index = 0
        self._state = "start"  # start, key_or_end, key, colon, value_start, value, done
        self._key: str | None = None
        self._key_start = 0
        self._value_start = 0
        self._depth = 0  # how deep the current value nests objects and arrays
        self._in_string = False
        self._escaped = False

    @property
    def done(self) -> bool:
        """Whether the whole object has been read."""
        return self._state == "done"

    def feed(self, text: str) -> list[tuple[str, Any]]:
        """Read more of the text, and return the properties whose values completed."""
        self._text += text
        found: list[tuple[str, Any]] = []
        while self._index < len(self._text) and self._state != "done":
            character = self._text[self._index]
            if self._state == "start":
                if character == "{":
                    self._state = "key_or_end"
            elif self._state == "key_or_end":
                if character == '"':
                    self._state, self._key_start, self._escaped = "key", self._index, False
                elif character == "}":
                    self._state = "done"
            elif self._state == "key":
                if self._escaped:
                    self._escaped = False
                elif character == "\\":
                    self._escaped = True
                elif character == '"':
                    self._key = _string_or_none(self._text[self._key_start : self._index + 1])
                    self._state = "colon"
            elif self._state == "colon":
                if character == ":":
                    self._state = "value_start"
            elif self._state == "value_start":
                if not character.isspace():
                    self._state, self._value_start = "value", self._index
                    self._depth, self._in_string, self._escaped = 0, False, False
                    continue  # this character is the value's first
            elif self._state == "value":
                self._read_value(character, found)
            self._index += 1
        return found

    def _read_value(self, character: str, found: list[tuple[str, Any]]) -> None:
        if self._in_string:
            if self._escaped:
                self._escaped = False
            elif character == "\\":
                self._escaped = True
            elif character == '"':
                self._in_string = False
        elif character == '"':
            self._in_string = True
        elif character in "{[":
            self._depth += 1
        elif character in "}]":
            if self._depth == 0:  # the end of the object itself
                self._hand_over(found)
                self._state = "done"
            else:
                self._depth -= 1
        elif character == "," and self._depth == 0:
            self._hand_over(found)
            self._state = "key_or_end"

    def _hand_over(self, found: list[tuple[str, Any]]) -> None:
        if self._key is None:
            return
        try:
            found.append((self._key, json.loads(self._text[self._value_start : self._index])))
        except ValueError:
            pass  # an unreadable value: left out


def _string_or_none(literal: str) -> str | None:
    try:
        value = json.loads(literal)
    except ValueError:
        return None
    return value if isinstance(value, str) else None
