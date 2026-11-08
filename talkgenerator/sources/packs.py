"""Content packs: the classic texts of a talk format, as versioned data (docs/v5-plan.md, section 11; decision D52).

A format's pack is a folder of `data/packs`, named after the format: `ted` is the TED talk's, which the default, ted,
interview and test schemas share. It has a grammar per kind of slide (`title.json`, `about_me.json`, `quiz.json`...),
whose rules are lists of templates, and a manifest, `pack.json`: the pack's version, what changed in each version, and
its slots, the rules the code fills in ("quiz.quiz_question"), each with the variables its templates may use and the
text field of a slide that its texts go in (see talkgenerator.plan.kinds), whose length they keep to.

A template names a variable with talkgenerator's functions on it ("{seed.generic}": see
talkgenerator.sources.text_generator.known_functions), and another rule of its grammar as tracery does
("#positive_word#"). A slot's generator picks one of its rule's templates with the current random stream and fills it
in, or tries another when it can't (a variable it lacks, a function that gives nothing): `tracery` expands it as tracery
does (and tries again, up to 100 times), and `templates` picks among the templates that are left (as v4 read its text
files). Every rule's name is the pack's only one, and a slot names it with its grammar's: "karaoke.dare".

Templates speak of a slide's topic as English does, as it may be "penguins", "coffee", "the moon" or "Belgium":
"{seed.generic}" after a verb or a preposition ("Love penguins", "Love coffee"), "{seed.one}" for one of it ("Get a
penguin"), and "{seed.bare}" after a word of the template's own, such as an article or an adjective, or before another
noun ("The moon paradox", "a penguin expert"); never with a verb after it that has to agree with it.

The version goes up whenever the texts change, with a line on what changed. Tests lint every pack
(tests/test_content_pack.py): every template fills in with its slot's variables, keeps to its field's length with long
words, has no word of the blocklists and speaks of its topic as English does, and no rule has a template twice.
"""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from talkgenerator.util import os_util

FOLDER: Final = "data/packs"
MANIFEST: Final = "pack.json"
TED: Final = "ted"  # (the TED talk's pack, the one there is for now)

# A slot's generator: a presentation context (the slide's "seed", and so on) in, a text out (or None)
TextGenerator = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class Slot:
    """A rule that the code fills in, by its full name ("quiz.quiz_question") or a pattern of them
    ("karaoke.buzzword_*"): the variables its templates may use, and how long its texts may be, as a text field of a
    kind of slide ("quiz.question") or a limit of its own; and for the captions of a row of pictures, how many captions
    a text has (separated by |), each as long as the field (0: as many as its rule's own, a meme template's boxes)."""

    name: str
    variables: tuple[str, ...] = ()
    field: str | None = None
    limit: int | None = None
    parts: int = 1

    def matches(self, rule: str) -> bool:
        return fnmatch.fnmatchcase(rule, self.name)


@dataclass(frozen=True)
class Pack:
    format: str
    version: int
    versions: Mapping[str, str]  # (by version: when it came, and what changed)
    slots: tuple[Slot, ...]

    def grammars(self) -> tuple[str, ...]:
        """The names of its grammars (its files but the manifest), in alphabetical order."""
        return _grammar_names(self.format)

    def grammar(self, name: str) -> dict[str, list[str]]:
        """A grammar's rules, by their names. Shared: never change them."""
        return _grammar(self.format, name)

    def rule(self, name: str) -> list[str]:
        """A rule's templates, by its full name ("karaoke.dare"). Shared: never change them."""
        grammar, rule = _split(name)
        return self.grammar(grammar)[rule]

    def has(self, name: str) -> bool:
        """Whether the pack has a rule, by its full name."""
        grammar, rule = _split(name)
        return grammar in self.grammars() and rule in self.grammar(grammar)

    def slot(self, name: str) -> Slot | None:
        """The slot of a rule, by its full name: the first that names it, if any does."""
        return next((slot for slot in self.slots if slot.matches(name)), None)

    def tracery(self, name: str) -> TextGenerator:
        """A generator of the rule's texts, expanded as tracery does (by its full name)."""
        from talkgenerator.sources import text_generator  # (here: it loads the text sources, and memes needs this)

        grammar, rule = _split(name)
        generate: TextGenerator = text_generator.TraceryTextGenerator(self.grammar(grammar), rule).generate
        return generate

    def templates(self, name: str) -> TextGenerator:
        """A generator of the rule's texts, each from one of its templates that are left (by its full name)."""
        from talkgenerator.sources import text_generator

        grammar, _ = _split(name)
        generator = text_generator.TemplatedTextGenerator(templates_list=self.rule(name), rules=self.grammar(grammar))
        generate: TextGenerator = generator.generate
        return generate


def _split(name: str) -> tuple[str, str]:
    grammar, _, rule = name.partition(".")
    if not grammar or not rule:
        raise ValueError(f"a rule's full name is its grammar's and its own, such as 'karaoke.dare': not {name!r}")
    return grammar, rule


@cache
def pack(name: str = TED) -> Pack:
    """A format's pack, by the format's name (the TED talk's by default)."""
    with open(os_util.to_actual_file(f"{FOLDER}/{name}/{MANIFEST}"), encoding="utf-8") as file:
        manifest = json.load(file)
    slots = tuple(
        Slot(
            name=slot,
            variables=tuple(spec.get("variables", ())),
            field=spec.get("field"),
            limit=spec.get("limit"),
            parts=int(spec.get("parts", 1)),
        )
        for slot, spec in manifest["slots"].items()
    )
    return Pack(
        format=str(manifest["format"]),
        version=int(manifest["version"]),
        versions={str(version): str(what) for version, what in manifest["versions"].items()},
        slots=slots,
    )


def formats() -> tuple[str, ...]:
    """The formats that have a pack, in alphabetical order."""
    folder = Path(os_util.to_actual_file(FOLDER))
    return tuple(sorted(path.parent.name for path in folder.glob(f"*/{MANIFEST}")))


@cache
def _grammar_names(format_name: str) -> tuple[str, ...]:
    folder = Path(os_util.to_actual_file(f"{FOLDER}/{format_name}"))
    return tuple(sorted(path.stem for path in folder.glob("*.json") if path.name != MANIFEST))


@cache
def _grammar(format_name: str, name: str) -> dict[str, list[str]]:
    with open(os_util.to_actual_file(f"{FOLDER}/{format_name}/{name}.json"), encoding="utf-8") as file:
        rules: dict[str, list[str]] = json.load(file)
    return rules
