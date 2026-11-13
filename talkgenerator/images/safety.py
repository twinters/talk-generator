"""talkgenerator's own rules for generated pictures (docs/v5-plan.md, section 10.5), on top of the providers' moderation:
no real, identifiable people, no logos or trademarked characters, and no gore or sexual content.

- A prompt that breaks them is never sent: `screen` says why, and the slide keeps its stock photo (or is made another
  way). It's turned down when it names a real person talkgenerator knows of (see talkgenerator.names.real_person), a
  brand or a trademarked character, someone famous in general ("a celebrity"), the talk's own presenter, gore or
  sexual content, or anything a slide shouldn't make light of (a faith, violence, hate: see
  talkgenerator.sources.slide_texts.sensitive).
- Every prompt that's sent carries them too (`avoid`): written into it for models that follow instructions, and as a
  negative prompt on local servers, which have no moderation of their own.
- The topic screening applies too: a talk whose topic a slide shouldn't make light of generates no pictures at all
  (`screen_topic`), and a talk whose topic the language model flags as unsafe is classic, and generates none either.

The lists can't know every name and brand; the providers' moderation is the next line.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Final

# What every generated picture leaves out (and, but on a book cover or a poster, writing: models garble it)
AVOID: Final = (
    "real or famous people, the likeness of anyone real, logos, brand names, trademarked characters, gore, nudity, "
    "sexual content"
)
AVOID_TEXT: Final = "text, letters, captions, watermarks"
# Brands and trademarked characters that prompts reach for (whole words or phrases, without accents)
_TRADEMARKS: Final = frozenset(
    {
        # characters
        "mickey mouse",
        "minnie mouse",
        "donald duck",
        "pikachu",
        "pokemon",
        "super mario",
        "zelda",
        "sonic the hedgehog",
        "hello kitty",
        "barbie",
        "shrek",
        "simpsons",
        "spongebob",
        "snoopy",
        "garfield",
        "scooby doo",
        "bugs bunny",
        "looney tunes",
        "batman",
        "superman",
        "spiderman",
        "spider man",
        "wonder woman",
        "iron man",
        "captain america",
        "hulk",
        "avengers",
        "darth vader",
        "yoda",
        "star wars",
        "stormtrooper",
        "harry potter",
        "hogwarts",
        "gandalf",
        "teletubbies",
        "peppa pig",
        "paw patrol",
        "elmo",
        "muppets",
        "kermit",
        "james bond",
        "pac man",
        "tetris",
        "minecraft",
        "fortnite",
        "roblox",
        # companies and brands
        "disney",
        "pixar",
        "marvel",
        "dc comics",
        "nintendo",
        "playstation",
        "xbox",
        "lego",
        "coca cola",
        "pepsi",
        "mcdonalds",
        "mcdonald s",
        "burger king",
        "starbucks",
        "nike",
        "adidas",
        "gucci",
        "louis vuitton",
        "chanel",
        "rolex",
        "ferrari",
        "lamborghini",
        "porsche",
        "ikea",
        "red bull",
        "nutella",
        "google",
        "microsoft",
        "facebook",
        "instagram",
        "tiktok",
        "youtube",
        "netflix",
        "twitter",
        "iphone",
        "ipad",
        "macbook",
        "logo",
        "logos",
        "trademark",
        "trademarked",
        "branded",
    }
)
# Someone famous, without a name
_FAMOUS: Final = frozenset(
    {
        "celebrity",
        "celebrities",
        "famous person",
        "famous people",
        "movie star",
        "film star",
        "pop star",
        "lookalike",
        "look alike",
        "likeness",
        "real person",
        "real people",
        "president",
        "prime minister",
        "politician",
        "royal family",
        "the queen",
        "the king",
    }
)
# Gore and sexual content (beside the words a slide shouldn't make light of, which have some of them)
_UNSAFE: Final = frozenset(
    {
        "gore",
        "gory",
        "blood",
        "bloody",
        "bleeding",
        "corpse",
        "corpses",
        "dead body",
        "dead bodies",
        "decapitated",
        "beheaded",
        "dismembered",
        "mutilated",
        "wound",
        "wounds",
        "injured",
        "naked",
        "nude",
        "nudity",
        "topless",
        "undressed",
        "lingerie",
        "underwear",
        "bikini",
        "erotic",
        "sexy",
        "seductive",
        "nsfw",
        "porn",
        "fetish",
    }
)
# What a found picture's description (a post's title, a photo's caption) may not say, beside the sources' own filters
# (such as Reddit's NSFW mark): nothing of nudity or sex (D80: r/OldSchoolCool's "Isaac Hayes Eating Fried Chicken Off
# of a Naked Woman", which Reddit doesn't mark, came up on a kindergarten teacher's slide), porn or gore; but a naked
# mole-rat may come, and a comet to the naked eye
_UNSAFE_DESCRIPTION: Final = re.compile(
    r"\b(?:nsfw|nudes?|nudity|naked(?![\s-]+(?:mole|eye))|topless|nipples?|boobs?|erotic\w*|porn\w*|sex|sexy"
    r"|strippers?|playboy|hentai|gore|gory)\b",
    re.IGNORECASE,
)


def unsafe_description(description: str | None) -> bool:
    """Whether a found picture's description says it's no picture for a slide (see _UNSAFE_DESCRIPTION)."""
    return bool(description) and _UNSAFE_DESCRIPTION.search(description or "") is not None


def avoid(writing: bool = False) -> str:
    """What a picture is to leave out: the rules, and writing unless it's to have some (a book cover's title)."""
    return AVOID if writing else f"{AVOID}, {AVOID_TEXT}"


def screen(prompt: str, private: Iterable[str] = ()) -> str | None:
    """Why the prompt mustn't go to an image generator, or None if it may: it names a real person talkgenerator knows
    of, someone famous, a brand or a trademarked character, gore or sexual content, something a slide shouldn't make
    light of, or a private name (the talk's presenter's)."""
    from talkgenerator import names  # (here: names imports what imports this module)
    from talkgenerator.sources.slide_texts import sensitive

    plain = _plain(prompt)
    for name in private:
        if name and _plain(name) and f" {_plain(name)} " in f" {plain} ":
            return "it names the talk's presenter"
    person = names.real_person(prompt)
    if person is not None:
        return f"it names a real person ({person})"
    for words, why in ((_TRADEMARKS, "a brand or a trademarked character"), (_FAMOUS, "someone famous")):
        found = _phrase_in(plain, words)
        if found is not None:
            return f"it names {why} ({found})"
    found = _phrase_in(plain, _UNSAFE)
    if found is not None:
        return f"it asks for gore or sexual content ({found})"
    if sensitive(prompt):
        return "it has words a slide shouldn't make light of"
    return None


def screen_topic(topics: Iterable[str]) -> str | None:
    """Why a talk on these topics generates no pictures, or None if it may."""
    from talkgenerator.sources.slide_texts import sensitive

    for topic in topics:
        if sensitive(topic):
            return f"its topic, {topic!r}, is one a slide shouldn't make light of"
        why = screen(topic)
        if why is not None:
            return f"its topic, {topic!r}: {why}"
    return None


def _plain(text: str) -> str:
    """The text in lower case, without accents, its words separated by single spaces (so "Coca-Cola" is "coca
    cola", and "McDonald's" "mcdonald s")."""
    unaccented = "".join(
        character for character in unicodedata.normalize("NFKD", text) if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", unaccented.casefold()))


def _phrase_in(plain: str, phrases: Iterable[str]) -> str | None:
    padded = f" {plain} "
    return next((phrase for phrase in sorted(phrases) if f" {phrase} " in padded), None)
