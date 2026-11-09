"""The content packs' lint (docs/v5-plan.md, section 11; decision D54).

A format's pack (talkgenerator/data/packs/<format>: see talkgenerator.sources.packs) is data, which these tests check:
its manifest names its version and its slots, every rule is a slot or used by one, and every template

- fills in with its slot's variables, through talkgenerator's functions, without leftovers;
- keeps to the length of its slot's text field, with long words in its variables;
- has no word of the blocklists (what a slide shouldn't make light of, gore, brands, real people, insults, and death,
  war and drink);
- speaks of its topic as English does: a slide's topic may be "penguins", but "coffee", "the moon", "Belgium" or "a plant
  that won't die" too, so a template says "{seed.generic}" after a verb or a preposition ("Love penguins", "Love
  coffee"), "{seed.one}" for one of it ("Get a penguin"), and "{seed.bare}" after a word of its own, such as an article
  or an adjective, or before another noun ("The moon paradox", "a penguin expert"), never the topic as it stands, nor a
  verb that has to agree with it;

and no rule has a template twice.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from tracery.modifiers import base_english

from talkgenerator import names
from talkgenerator.images import safety
from talkgenerator.plan.kinds import KINDS
from talkgenerator.sources import memes, packs, slide_texts, text_generator

FORMATS = packs.formats()
_REFERENCE = re.compile(r"#([^#.]+)((?:\.\w+)*)#")
_PLACEHOLDER = re.compile(r"\{(\w+)((?:\.\w+)*)\}")

# Long values of the variables a slot may have, to check that its texts fit their fields: words of 22 to 24 letters
# (as long as the related words a slide takes), as a countable noun (its plural is longer), a mass noun and a phrase
# with an article; a long name, title and wikiHow action
LONG: dict[str, tuple[str, ...]] = {
    "seed": ("conference interpreter", "artificial intelligence", "the French Revolution"),
    "related": ("conference interpreter", "artificial intelligence", "photosynthesis research"),
    "topic": ("conference interpreter", "artificial intelligence", "the French Revolution"),
    "x_label": ("conference interpreter", "artificial intelligence", "the French Revolution"),
    "y_label": ("conference interpreter", "artificial intelligence", "the French Revolution"),
    "presenter": ("Dr. Bartholomew Featherstone",),
    "title": ("The Surprising Science of Conference Interpreters",),
    "action": ("Build a Birdhouse Out of Old Books",),
    "chart_title": ("Would you accept it if your loved one started to build a birdhouse?",),
    "number": ("99",),
    "percent": ("97%",),
    "year": ("2003",),
    "acronym": ("SPARKS",),
    # (the made-up names of a pitch's startup, an academic talk's method, an all-hands' company and a keynote's
    # product, at their longest: see talkgenerator.schema.formats.startup, method, company and product)
    "startup": ("Overinterpreting Labs",),
    "method": ("OverinterpretingFormer",),
    "company": ("Overinterpreting Holdings",),
    "product": ("Overinterpreting Studio",),
    # (a real dad joke and a real piece of advice, at the longest talkgenerator.facts takes them)
    "joke": ("Why did the scarecrow win an award at the big harvest fair? He was outstanding in it.",),
    "advice": ("Always double check you actually attached the file to emails",),
    # (a reference's figure and page, as an academic talk's caption has them: "[3], Fig. 9", "[2], p. 399")
    "figure": ("9",),
    "page": ("399",),
}
# Topics of every kind, to check that every template reads right with each: a countable noun, a mass noun, a plural, a
# name, a phrase with an article, two words, a premise with a clause of its own, and a phrase with words about its
# noun after it
SEEDS: tuple[dict[str, str], ...] = tuple(
    {"seed": seed, "topic": seed, "related": related, "x_label": related, "y_label": seed}
    for seed, related in (
        ("penguin", "feather"),
        ("coffee", "milk"),
        ("penguins", "socks"),
        ("Belgium", "waffle"),
        ("the moon", "cheese"),
        ("time travel", "clocks"),
        ("a plant that won't die", "soil"),
        ("a message in a bottle", "beach"),
    )
)
COMMON = {
    "presenter": "Ann Wells",
    "title": "The Hidden Life of Penguins",
    "action": "Make a Paper Boat",
    "chart_title": "Would you like to make a paper boat?",
    "number": "12",
    "percent": "40%",
    "year": "1823",
    "acronym": "PEN",
    "startup": "Penguinly",
    "method": "PenguinNet",
    "company": "Penguin Corp",
    "product": "Penguin Pro",
    "joke": "What do you call a penguin in the desert? Lost.",
    "advice": "Don't eat non-snow-coloured snow.",
    "figure": "3",
    "page": "42",
}
# What the functions that ask the internet give, in these tests: a long wikiHow action, and for the moon a short one,
# which a template that makes one word of an action takes (a longer one gives way, see text_generator.LONGEST_WORD)
OFFLINE = {
    "wikihow_action": lambda seed: "fly a kite" if seed == "the moon" else "build a birdhouse out of old books",
    "conceptnet_location": lambda word: "the bottom of the ocean",
    "conceptnet_related": lambda word: "interpreter",
    "conceptnet_related_single_word": lambda word: "interpreter",
}

# Variables that name a thing, which can be singular, plural, a name or a phrase with an article
NOUNS = frozenset({"seed", "related", "topic", "x_label", "y_label"})
# Functions that make something else of a variable (an action, a related word): what comes out isn't the topic
CONVERTERS = frozenset(
    {"wikihow_action", "conceptnet_location", "conceptnet_related", "conceptnet_related_single_word", "first_letter"}
    | {"get_last_noun_and_article", "is_verb", "ing"}
)
# Functions that speak of a thing as English does, and the one for a thing before another noun
SPOKEN = frozenset({"generic", "one"})
BEFORE_A_NOUN = "bare"
# Functions that guess the number of a thing, which English often gets wrong ("coffees", "Belgiums", "octopu")
GUESSES = frozenset({"plural", "singular", "a"})
# Words that a thing spoken of as English does (generic, one) can't follow, as it may have an article of its own ("the
# moon") or be one or many ("penguins", "coffee"): articles, possessives, quantifiers, numbers and adjectives. (After
# them, a template says the thing without its article: "{seed.bare}".)
_BEFORE = re.compile(
    r"(?:^|[^\w'])(the|a|an|my|your|our|their|his|her|its|these|those|every|each|no|some|any|another|which|whose|"
    r"many|much|few|fewer|several|both|more|less|most|enough|one|two|three|four|five|ten|\d+%?|"
    r"\{(?:number|percent)\}|bad|good|better|best|worse|worst|real|true|fake|new|old|great|little|big|small|tiny|"
    r"giant|huge|perfect|ideal|typical|average|normal|ordinary|weird|strange|secret|hidden|happy|sad|modern|ancient|"
    r"future|first|last|next|cheap|expensive|pure|single|whole|entire|actual)\s+$",
    re.IGNORECASE,
)
# A verb that has to agree with the thing after it, as a question or a sentence starts ("Is coffee...", "What are
# penguins?"); after a subject of its own, it agrees with that ("the answer is penguins")
_ASKING = re.compile(
    r"(?:^|[.!?:]\s+|\b(?:what|where|why|how|who|when|which|whose)\s+)"
    r"(is|are|was|were|has|have|does|do|isn't|aren't|wasn't|weren't|hasn't|haven't|doesn't|don't)\s+$",
    re.IGNORECASE,
)
# Words that make a thing one: after them, a thing without its article has to stand before a noun ("a penguin expert",
# never "a penguins")
_ONE = re.compile(r"\b(?:a|an|one|each|every|another|single)\s+(?:\S+\s+){0,2}$", re.IGNORECASE)
# Verbs that have to agree with a thing after it ("penguins are", but "coffee is")
AGREEING = frozenset(
    "is are was were has have does do isn't aren't wasn't weren't hasn't haven't doesn't don't 's seems seem looks "
    "look makes make needs need goes go gets get takes take comes come deserves deserve exists exist lives live costs "
    "cost means mean matters matter remains remain wants want knows know says say likes like hates hate loves love "
    "works work keeps keep gives give holds hold runs run changes change rules rule wins win beats beat saves save "
    "controls control belongs belong sounds sound tastes taste feels feel smells smell happens happen".split()
)
# Words after which a verb has its base form, whatever its subject: "Can penguins make...?", "Will coffee save us?"
_MODAL = re.compile(r"\b(?:can|could|would|will|should|may|might|must|shall|let|make|help|watch)\s+$", re.IGNORECASE)
# Of the verbs that agree, the ones that are base forms too ("make", but not "makes")
BASE_FORMS = frozenset(word for word in AGREEING if not word.endswith(("s", "'t")) and word not in ("are", "were"))
# Words that a thing without its article can't stand before, after a word that makes it one: it'd be the thing itself
FUNCTION_WORDS = frozenset(
    "a an the and or but nor of in on at to for with by from into onto about over under than as so if then that "
    "this these those is are was were be".split()
)
# Insults and swear words, and what a family audience doesn't need at a talk (death, war, drink), beside the
# blocklists of slides (talkgenerator.sources.slide_texts) and of generated pictures (talkgenerator.images.safety)
HURTFUL = frozenset(
    "damn hell crap shit fuck fucking piss ass arse bitch bastard dick sucks stupid idiot idiots dumb moron morons "
    "loser losers ugly fat fatty obese crazy insane psycho lunatic retard retarded lame cripple midget freak freaks "
    "weirdo die dies died dead dying deadly war wars army soldier soldiers drunk alcohol beer wine vodka whisky "
    "hangover cult cancer disease sick pandemic".split()
)
# Texts that no topic should come out as
_SLIPS = re.compile(
    r"\b(?:the|a|an) (?:the|a|an)\b|\bcoffees\b|\bbelgiums\b|\bthe moons\b|\btime travels\b|\ban? (?:penguins|socks)\b",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    for name, fake in OFFLINE.items():
        monkeypatch.setitem(text_generator.known_functions, name, fake)


def _slots(pack: packs.Pack) -> Iterator[tuple[packs.Slot, str]]:
    """Every rule that's a slot, with its slot."""
    for grammar in pack.grammars():
        for rule in pack.grammar(grammar):
            slot = pack.slot(f"{grammar}.{rule}")
            if slot is not None:
                yield slot, f"{grammar}.{rule}"


def _limit(slot: packs.Slot) -> int:
    if slot.limit is not None:
        return slot.limit
    assert slot.field is not None, slot
    kind, name = slot.field.split(".")
    return next(text.max_length for text in KINDS[kind].texts if text.name == name)


def _references(template: str) -> list[str]:
    return [match.group(1) for match in _REFERENCE.finditer(template)]


def _reached(pack: packs.Pack, grammar: str, rule: str) -> set[str]:
    """The rules a rule uses, and the rules those use, and so on (itself included)."""
    rules = pack.grammar(grammar)
    seen = {rule}
    todo = [rule]
    while todo:
        for template in rules[todo.pop()]:
            for reference in _references(template):
                if reference not in seen:
                    seen.add(reference)
                    todo.append(reference)
    return seen


def _modified(text: str, modifiers: str) -> str:
    for modifier in [name for name in modifiers.split(".") if name]:
        text = base_english[modifier](text)
    return text


@cache
def _samples(format_name: str, grammar: str, rule: str) -> tuple[str, ...]:
    """Expansions of a rule's templates that, together, use every template of every rule it uses (rules expanded,
    variables left as they are)."""
    rules = packs.pack(format_name).grammar(grammar)
    expanded: list[str] = []
    for template in rules[rule]:
        references = list(_REFERENCE.finditer(template))
        choices = [_samples(format_name, grammar, match.group(1)) for match in references]
        for index in range(max([len(options) for options in choices], default=1)):
            text = template
            for match, options in reversed(list(zip(references, choices, strict=True))):
                text = (
                    text[: match.start()]
                    + _modified(options[index % len(options)], match.group(2))
                    + text[match.end() :]
                )
            expanded.append(text)
    return tuple(expanded)


def _filled(template: str, variables: dict[str, str]) -> str | None:
    return text_generator.apply_variables_to_template(template, dict(variables))


def _longest(format_name: str, grammar: str, rule: str, variables: dict[str, str]) -> list[int]:
    """How long the rule's texts can be with these variables, per caption (a text of a row of pictures has one per
    picture, separated by |): its longest template with its rules' longest texts in it."""
    best: list[int] = []
    for template in _samples(format_name, grammar, rule):
        filled = _filled(template, variables)
        if filled:
            lengths = [len(part) for part in filled.split("|")]
            best = [max(pair) for pair in itertools.zip_longest(best, lengths, fillvalue=0)]
    return best


def _literal(template: str) -> str:
    """The template's own words: without its variables and rules."""
    return _REFERENCE.sub(" ", _PLACEHOLDER.sub(" ", template))


# THE MANIFEST


def test_there_is_a_ted_pack():
    assert packs.TED in FORMATS


@pytest.mark.parametrize("format_name", FORMATS)
def test_the_manifest_says_what_every_version_changed_and_what_every_slot_takes(format_name):
    pack = packs.pack(format_name)
    assert pack.format == format_name and pack.version >= 1
    assert sorted(pack.versions, key=int) == [str(version) for version in range(1, pack.version + 1)]
    assert all(what.strip() for what in pack.versions.values())
    for slot in pack.slots:
        assert slot.parts >= 0 and (slot.field is None) != (slot.limit is None), slot
        assert set(slot.variables) <= set(LONG), slot  # (a variable these tests know long values of)
        _limit(slot)  # (a text field of a kind of slide, or a limit of its own)


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_slot_has_rules_and_the_code_fills_it_in(format_name):
    pack = packs.pack(format_name)
    rules = {f"{grammar}.{rule}" for grammar in pack.grammars() for rule in pack.grammar(grammar)}
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path(packs.__file__).parents[1].rglob("*.py"))
    for slot in pack.slots:
        assert any(slot.matches(rule) for rule in rules), slot.name
        named = slot.name.split("*")[0] if "*" in slot.name else f'{slot.name}"'  # (of a pattern, its start)
        assert f'"{named}' in source, f"no code fills in {slot.name}"


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_rule_is_a_slot_or_used_by_one_and_named_once(format_name):
    pack = packs.pack(format_name)
    used: set[tuple[str, str]] = set()
    names_seen: dict[str, str] = {}
    for grammar in pack.grammars():
        rules = pack.grammar(grammar)
        assert rules and all(isinstance(rule, str) for rule in rules)
        for rule, templates in rules.items():
            assert rule not in names_seen, f"{rule} is in {grammar} and in {names_seen[rule]}"
            names_seen[rule] = grammar
            assert isinstance(templates, list) and templates and all(isinstance(text, str) for text in templates)
            for template in templates:
                assert all(reference in rules for reference in _references(template)), (grammar, rule, template)
            if pack.slot(f"{grammar}.{rule}") is not None:
                used |= {(grammar, reached) for reached in _reached(pack, grammar, rule)}
    unused = [f"{grammar}.{rule}" for grammar in pack.grammars() for rule in pack.grammar(grammar)]
    assert [rule for rule in unused if tuple(rule.split(".", 1)) not in used] == []


# EVERY TEMPLATE


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_template_uses_its_slots_variables_through_known_functions(format_name):
    pack = packs.pack(format_name)
    wrong = []
    for slot, name in _slots(pack):
        grammar, rule = name.split(".")
        for reached in _reached(pack, grammar, rule):
            for template in pack.grammar(grammar)[reached]:
                for variable, functions in _PLACEHOLDER.findall(template):
                    unknown = [f for f in functions.split(".")[1:] if f not in text_generator.known_functions]
                    if variable not in slot.variables or [f for f in unknown if not f.isdigit()]:
                        wrong.append(f"{name} ({reached}): {template}")
    assert wrong == []


@pytest.mark.parametrize("format_name", FORMATS)
@pytest.mark.slow
def test_every_template_fills_in_for_every_kind_of_topic(format_name):
    pack = packs.pack(format_name)
    empty, leftovers = [], []
    for slot, name in _slots(pack):
        grammar, rule = name.split(".")
        for template in _samples(format_name, grammar, rule):
            texts = [_filled(template, {**COMMON, **seed}) for seed in SEEDS]
            if not any(texts):
                empty.append(f"{name}: {template}")
            for text in filter(None, texts):
                parts = text.split("|")
                if (
                    len(parts) != slot.parts != 0  # (0: as many as its rule's own, a meme template's boxes)
                    or any(not part.strip() or part != part.strip() for part in parts)
                    or re.search(r"[{}#]|  | [,.!?:;]", text)
                ):
                    leftovers.append(f"{name}: {text!r}")
    assert empty == [] and leftovers == []


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_text_keeps_to_its_fields_length_with_long_words(format_name):
    pack = packs.pack(format_name)
    long = []
    for slot, name in _slots(pack):
        grammar, rule = name.split(".")
        limit = _limit(slot)
        if slot.parts == 0:  # (a meme's captions: each as long as its box allows, see the memes' test)
            continue
        for index in range(3):
            variables = {variable: values[index % len(values)] for variable, values in LONG.items()}
            for length in _longest(format_name, grammar, rule, variables):
                if length > limit:
                    worst = max(
                        (_filled(template, variables) or "" for template in _samples(format_name, grammar, rule)),
                        key=lambda text: max(len(part) for part in text.split("|")),
                    )
                    long.append(f"{name} ({limit}): {worst}")
    assert sorted(set(long)) == []


@pytest.mark.parametrize("format_name", FORMATS)
def test_no_template_has_a_word_of_the_blocklists(format_name):
    pack = packs.pack(format_name)
    blocked = []
    for grammar in pack.grammars():
        for rule, templates in pack.grammar(grammar).items():
            for template in templates:
                words = _literal(template)
                plain = safety._plain(words)
                if (
                    slide_texts.sensitive(words)
                    or safety._phrase_in(plain, safety._UNSAFE | safety._TRADEMARKS) is not None
                    or names.real_person(words) is not None
                    or HURTFUL & set(plain.split())
                ):
                    blocked.append(f"{grammar}.{rule}: {template}")
    assert blocked == []


@pytest.mark.parametrize("format_name", FORMATS)
def test_no_rule_has_a_template_twice(format_name):
    pack = packs.pack(format_name)
    twice = []
    for grammar in pack.grammars():
        for rule, templates in pack.grammar(grammar).items():
            seen: set[str] = set()
            for template in templates:
                if not _REFERENCE.sub("", template).replace("|", ""):  # (rules named again: a weight)
                    continue
                key = re.sub(r"[ \t]+", " ", template.casefold()).strip(" .")
                if key in seen:
                    twice.append(f"{grammar}.{rule}: {template}")
                seen.add(key)
    assert twice == []


def _spoken_wrongly(template: str) -> list[str]:
    """What's wrong with how a template speaks of the things its variables name (see the module's documentation)."""
    wrong = []
    for match in _PLACEHOLDER.finditer(template):
        variable, functions = match.group(1), [name for name in match.group(2).split(".") if name]
        if variable not in NOUNS or CONVERTERS & set(functions):
            continue
        before, after = template[: match.start()], template[match.end() :]
        quoted = before[-1:] in "'\"" and after[:1] in "'\""
        following = re.match(r"\s*([\w']+)", after)
        next_word = following.group(1).lower() if following and after[:1] == " " else None
        if next_word in AGREEING and not (next_word in BASE_FORMS and _MODAL.search(before)):
            wrong.append(f"{match.group(0)} has a verb after it that has to agree with it ({next_word})")
        if _ASKING.search(before):
            wrong.append(f"{match.group(0)} has a verb before it that has to agree with it")
        if GUESSES & set(functions):
            wrong.append(f"{match.group(0)} guesses the number of what it names: say generic, one or bare")
        elif BEFORE_A_NOUN in functions:
            if _ONE.search(before) and (next_word is None or next_word in FUNCTION_WORDS | AGREEING):
                wrong.append(f"{match.group(0)} is made one, but stands before no noun")
        elif not SPOKEN & set(functions):
            if not quoted:
                wrong.append(f"{match.group(0)} says the topic as it is: say generic, one or bare")
        elif _BEFORE.search(before):
            wrong.append(f"{match.group(0)} has a word of its own before it: say bare")
    return wrong


@pytest.mark.parametrize("format_name", FORMATS)
@pytest.mark.slow
def test_every_template_speaks_of_its_topic_as_english_does(format_name):
    pack = packs.pack(format_name)
    wrong, slips = [], []
    for _slot, name in _slots(pack):
        grammar, rule = name.split(".")
        for template in _samples(format_name, grammar, rule):
            wrong += [f"{name}: {template}: {why}" for why in _spoken_wrongly(template)]
            for seed in SEEDS:
                text = _filled(template, {**COMMON, **seed})
                if text and _SLIPS.search(text):
                    slips.append(f"{name}: {text}")
    assert wrong == [] and slips == []


@pytest.mark.parametrize(
    ("template", "wrong"),
    [
        ("Love {seed.generic}", False),
        ("Is this {seed.one}?", False),
        ("The {seed.bare} paradox", False),
        ("The word '{seed}'", False),
        ("{seed.generic.cap} can't be seen from space", False),
        ("Bad {seed.bare}|Good {seed.bare}", False),  # ("Bad moon", "Bad penguins", "Bad coffee")
        ("My {seed.bare}", False),
        ("A {seed.bare} expert", False),
        ("Clearly, the answer is {seed.generic}", False),  # (the verb agrees with the answer)
        ("Can {seed.generic} make you happy?", False),  # (a base form, after "can")
        ("Where will {seed.generic} take us?", False),
        ("The {seed} paradox", True),  # ("The the moon paradox")
        ("Love {seed}", True),  # ("Love penguin")
        ("{seed.generic.cap} is overrated", True),  # ("Penguins is overrated")
        ("Is {seed.generic} the answer?", True),  # ("Is penguins the answer?")
        ("{seed.generic.cap} make it better", True),  # ("Coffee make it better")
        ("Can {seed.generic} makes you happy?", True),
        ("What is {seed.generic}?", True),
        ("There are many {seed.generic}", True),  # ("many coffee")
        ("My {seed.generic}", True),  # ("My the moon")
        ("Bad {seed.generic}", True),  # ("Bad the moon")
        ("A very tired {seed.bare}", True),  # ("A very tired penguins")
        ("All about {seed.plural}", True),  # ("coffees")
        ("{number} {seed.generic}", True),  # ("12 coffee")
        ("Astro{seed.title.last_letter_is_consonant}ography", True),  # ("AstroThe Moonography")
    ],
)
def test_how_the_lint_tells_a_topic_spoken_of_wrongly(template, wrong):
    assert bool(_spoken_wrongly(template)) == wrong


# MEMES


def _with(grammar: str) -> list[str]:
    """The formats whose packs have the grammar (only TED-like talks have memes and karaoke's types, say)."""
    return [name for name in FORMATS if grammar in packs.pack(name).grammars()]


@pytest.mark.parametrize("format_name", _with("memes"))
def test_every_meme_template_has_captions_that_fit_its_boxes(format_name):
    captions = packs.pack(format_name).grammar("memes")
    known = memes.templates()
    assert set(captions) == {memes.rule_of(template.name) for template in known.values()}
    for template in known.values():
        written = template.written()
        for sentences in captions[memes.rule_of(template.name)]:
            parts = sentences.split("|")
            assert len(parts) == len(written), (template.name, sentences)
            for part, box in zip(parts, written, strict=True):
                for index in range(3):
                    variables = {variable: values[index % len(values)] for variable, values in LONG.items()}
                    filled = _filled(part, variables)
                    # (twice what its box holds at 40 pixels: a caption gets smaller to fit, down to 24)
                    assert filled and len(filled) <= 2 * max(12, template.room(box)), (template.name, filled)


# AN ACRONYM'S WORDS


@pytest.mark.parametrize("format_name", _with("karaoke"))
def test_an_acronyms_words_start_with_their_letter(format_name):
    karaoke = packs.pack(format_name).grammar("karaoke")
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for kind in ("buzzword", "absurd"):
            words = karaoke[f"{kind}_{letter.lower()}"]
            assert words and all(word[:1].upper() == letter or letter in word for word in words), (kind, letter)
    assert all(acronym.isalpha() and acronym.isupper() for acronym in karaoke["acronyms"])


# HOW MUCH THERE IS


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_slot_has_options(format_name):
    pack = packs.pack(format_name)
    few = []
    for slot, name in _slots(pack):
        grammar, rule = name.split(".")
        least = 3 if "*" in slot.name else 6  # (an acronym's words for a letter, say, and the texts of a slot)
        if len(set(_samples(format_name, grammar, rule))) < least:
            few.append(name)
    assert few == []
