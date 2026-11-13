"""The museum tour (docs/v5-plan.md, section 7; D79): a guided tour of a museum's collection about the talk's topic, as
a guide shows a group around, with hushed admiration for every exhibit, however unlikely.

Its arc goes from the welcome (the museum's hall, full-bleed, the house rules, or the tour's stops as an agenda)
through a masterpiece (a painting from a museum's collection under its label, full-bleed, or before and after a
restoration that went wrong), the artist (their life as a timeline, a fun fact, or their post from centuries ago), the
eras (three paintings of three periods, the art movements as a tier list, or the hierarchy of art as a pyramid) and an
artefact behind glass (an odd object, a quiz on what it was for, or the news of its discovery) to the gift shop (the
prices on tiles, one big price, or three souvenirs), before its closer thanks the room for visiting and points them to
the gift shop (D76), outside its slides. A short tour keeps its masterpiece, the gift shop, the artefact and the
welcome; a quarter of a talk's slides are free (D63), for memes, full-screen pictures, gifs, deep questions, quotes, the
museum's reviews and its own provocations ("Priceless.", over a full-screen picture); a long tour gives the masterpiece,
the artist and the eras a second slide. The museum's made-up name and its old master's come from the topic (see
talkgenerator.schema.formats.museum_name and artist), so that a classic tour's slides name the same museum and the same
artist.

Its paintings are public domain art from museums (the museum look), and a painting after its restoration is a clumsy
illustration of the same thing, so a tour needs no image that's fair use. No slide shows a portrait under the artist's
made-up name: a museum's portrait may be of someone real.

A museum guide gives a tour far more often than the other personas, a medieval historian more often, and an
over-passionate expert, an alien anthropologist and a time traveller a little more often; its themes are vintage paper
and clean keynotes more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import AGENDA_ITEM, Recipe, Variant, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    artist,
    behind,
    different,
    maybe,
    museum_name,
    photos,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.util import random_util

PACK: Final = "museum"

# (D63: a quarter of its slides are free, for memes, pictures and the like; the gift shop stays almost as long as the
# masterpiece, as the tour's ending)
ARC: Final = Arc(
    (
        Part("welcome", rank=3),
        Part("masterpiece", 1, 2, rank=0),
        Part("artist", 1, 2, rank=4),
        Part("eras", 1, 2, rank=5),
        Part("artefact", rank=2),
        Part("gift_shop", rank=1),
    ),
    free=0.25,
)

MUSEUM: Final = Format(
    brief="a guided tour of a museum's collection about the topic, as a guide shows a group around: the welcome and "
    "the house rules, a masterpiece, the artist and their life, the eras and movements of art, an artefact behind "
    "glass and the gift shop. Every exhibit, however unlikely, is about the topic, the artist is a made-up old master, "
    "and the guide speaks of each exhibit with hushed admiration: few words, big pictures of art",
    title_hint="like an exhibition's title: grand, with the museum's made-up name or a period of art",
    job_hint="their part at the museum, as the tour's leaflet introduces them (the head guide, the curator of an "
    "absurdly specific collection, a volunteer of thirty years)",
    personas={
        "museum_guide": 9,
        "medieval_historian": 2.5,
        "passionate_expert": 1.5,
        "alien_anthropologist": 1.5,
        "time_traveller": 1.5,
    },
    themes={
        "vintage paper": 4,
        "clean keynote": 2.5,
        "Swiss poster": 1.5,
        "academic": 1.3,
        "dark minimal": 1.3,
        "hacker terminal": 0.4,
        "neon": 0.4,
        "clip-art corporate": 0.5,
        "Comic Sans everywhere": 0.5,
        "startup": 0.5,
    },
    arc=ARC,
    # (its closer thanks the room for visiting, and points to the gift shop: D76)
    closer=Closer(said("visiting"), said("gift_shop"), presenter),
    scene="museum gallery",
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, the presenter, the title, and the
    museum's and its old master's made-up names."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    topic = str(context.get("topic") or context["seed"])
    variables["museum"] = museum_name(topic)
    variables["artist"] = artist(topic)
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


def _year() -> str:
    """A year an old master could have painted in, from the current random stream."""
    return str(random_util.randint(1480, 1890))


# THE TITLE SLIDE: the exhibition, and who guides the tour


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic tour's title, about the seed (the talk's topic)."""
    topic = str(context["seed"])
    return text(PACK, "title.talk_title", {**context, "museum": museum_name(topic), "artist": artist(topic)})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: the museum's hall, the topic's paintings and works of art from museums' collections (public domain), a
# painting after its restoration (a clumsy illustration of the same thing), an odd object behind glass, and
# souvenirs from the gift shop
_HALL = ImageSlot(
    "a photo of the museum's grand hall",
    queries=("{} museum", "museum gallery"),
    aesthetic="photo",
    backups=("museum",),
)
_PAINTING = ImageSlot(
    "a painting of the topic, from a museum's collection", aesthetic="museum", backups=("illustration",)
)
_RESTORED = ImageSlot(
    "the same painting after a restoration that went wrong: a clumsy drawing of the topic",
    aesthetic="illustration",
    backups=("weird-stock",),
)
# (searched as the topic's art first, so that the artist's works and periods are others than the masterpiece)
_ARTWORK = ImageSlot(
    "a work of art of the topic, from a museum's collection",
    queries=("{} art", "{}"),
    aesthetic="museum",
    backups=("photo",),
)
_OBJECT = ImageSlot(
    "an odd object of the topic, as a museum shows one behind glass", aesthetic="weird-stock", generate=True
)
_SOUVENIR = ImageSlot(
    "a souvenir of the topic, as a museum's gift shop sells one",
    queries=("{} souvenir", "{} toy", "{}"),
    aesthetic="photo",
)


# THE WELCOME: the museum's hall, full-bleed, the house rules, or the tour's stops


def _welcome(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "welcome.welcome_title", _variables(context))
    return ({"title": title}, {"image": _HALL(context)}) if title else None


def _house_rules(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 4)
    rules = different(PACK, "welcome.rule", variables, count - 1)
    last, title = text(PACK, "welcome.rule_punchline", variables), text(PACK, "welcome.rules_title", variables)
    if not title or not last or len(rules) < count - 1:
        return None
    return {"title": title, "items": " | ".join([*rules, last])}, {}


def _tour(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 4)
    first, last = text(PACK, "welcome.tour_first", variables), text(PACK, "welcome.tour_last", variables)
    stops = different(PACK, "welcome.stop", variables, count - 2)
    title = text(PACK, "welcome.tour_title", variables)
    if not title or not first or not last or len(stops) < count - 2:
        return None
    return {"title": title, "items": " | ".join([first, *stops, last])}, {}


# THE MASTERPIECE: a painting under its label, full-bleed, or before and after its restoration


def _labelled(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "masterpiece.label", {**_variables(context), "year": _year()})
    return ({"title": title}, {"image": _PAINTING(context)}) if title else None


def _full_bleed(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "masterpiece.full_title", {**_variables(context), "year": _year()})
    return ({"title": title}, {"image": _PAINTING(context)}) if title else None


def _restoration(context: dict[str, Any]) -> Made | None:
    variables = {**_variables(context), "year": _year()}
    before, after = text(PACK, "masterpiece.before", variables), text(PACK, "masterpiece.after", variables)
    if not before or not after:
        return None
    title = maybe(0.8, text(PACK, "masterpiece.restoration_title", variables))
    texts = {"title": title, "caption_1": before, "caption_2": after}
    return texts, {"image_1": _PAINTING(context), "image_2": _RESTORED(context)}


# THE ARTIST: their life, a fun fact, or their post from centuries ago


def _lifetime(count: int) -> list[str]:
    """The dates of the artist's life: years a dozen or two apart, oldest first, from a year an old master could have
    been born in; the last one, now and then, a moment of today's ("Last Tuesday")."""
    year = int(_year()) - random_util.randint(0, 60)
    dates = [str(year)]
    for _ in range(count - 2):
        year += random_util.randint(9, 24)
        dates.append(str(year))
    if random_util.random() < 0.4:
        return [*dates, random_util.choice(words(PACK, "artist.last_date"))]
    return [*dates, str(year + random_util.randint(6, 30))]


def _life(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(4, 5)
    born, last = text(PACK, "artist.born", variables), text(PACK, "artist.life_punchline", variables)
    middle = different(PACK, "artist.life_event", variables, count - 2)
    title = text(PACK, "artist.life_title", variables)
    if not title or not born or not last or len(middle) < count - 2:
        return None
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(_lifetime(count), [born, *middle, last], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


def _artist_fact(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    fact = text(PACK, "artist.fact", variables)
    if not fact:
        return None
    return {"fact": fact, "source": maybe(0.7, text(PACK, "artist.fact_source", variables))}, {
        "photo": _ARTWORK(context)
    }


def _handle(name: str) -> str:
    """The old master's username, from their made-up name ("janvanpenguin"), 24 characters at most."""
    base = "".join(letter for letter in name.lower() if letter.isalnum()) or "oldmaster"
    return random_util.choice((base, f"real{base}", f"{base}_paints", f"the{base}"))[:24]


def _artist_post(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "artist.post", variables)
    if not post:
        return None
    name = variables["artist"]
    texts = {
        "title": maybe(0.7, text(PACK, "artist.post_title", variables)),
        "author": name,
        "handle": _handle(name),
        "text": post,
    }
    return texts, {"photo": _ARTWORK(context)}


# THE ERAS: three paintings of three periods, the movements as a tier list, or the hierarchy of art


def _periods(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    periods = different(PACK, "eras.period", variables, 2)
    punchline = text(PACK, "eras.period_punchline", variables)
    if len(periods) < 2 or not punchline:
        return None
    texts = {
        "title": maybe(0.8, text(PACK, "eras.periods_title", variables)),
        **_items("caption", [*periods, punchline]),
    }
    return texts, {f"image_{index}": work for index, work in enumerate(photos(_ARTWORK, context, 3), 1)}


def _movements(context: dict[str, Any]) -> Made | None:
    """The art movements, ranked: the topic's own on top, the punchline, real and made-up ones in between, and the
    worst at the bottom."""
    variables = _variables(context)
    best, worst = text(PACK, "eras.s_tier", variables), text(PACK, "eras.f_tier", variables)
    movements = different(PACK, "eras.movement", variables, 5)
    title = text(PACK, "eras.tiers_title", variables)
    if not title or not best or not worst or len(movements) < 4:
        return None
    first = 2 if random_util.random() < 0.5 else 1  # (one or two in the A tier)
    tiers = [movements[:first], movements[first : first + 1], movements[first + 1 : first + 3]]
    return {
        "title": title,
        "s_tier": best,
        **{f"{tier}_tier": " | ".join(things) for tier, things in zip("abc", tiers, strict=True)},
        "f_tier": worst,
    }, {}


def _hierarchy(context: dict[str, Any]) -> Made | None:
    """The hierarchy of art as a pyramid: the topic at its top, the punchline, and the gift shop's at its base."""
    variables = _variables(context)
    top, base = text(PACK, "eras.pyramid_top", variables), text(PACK, "eras.pyramid_base", variables)
    levels = different(PACK, "eras.level", variables, 2 if random_util.random() < 0.6 else 1)
    title = text(PACK, "eras.pyramid_title", variables)
    if not title or not top or not base or not levels:
        return None
    return {"title": title, **_items("level", [top, *levels, base])}, {}


# THE ARTEFACT: an odd object behind glass, a quiz on what it was for, or the news of its discovery


def _artefact(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "artefact.artefact_title", {**_variables(context), "number": str(random_util.randint(2, 99))})
    return ({"title": title}, {"image": _OBJECT(context)}) if title else None


def _what_for(context: dict[str, Any]) -> Made | None:
    """A quiz on what people once used the topic for: two or three uses, and the museum's own answer, the punchline,
    which is the right one."""
    variables = _variables(context)
    question, right = text(PACK, "artefact.quiz_question", variables), text(PACK, "artefact.right_use", variables)
    wrong = different(PACK, "artefact.use", variables, 3 if random_util.random() < 0.6 else 2)
    if not question or not right or len(wrong) < 2:
        return None
    options = [*wrong]
    options.insert(random_util.randint(len(options) // 2, len(options)), right)  # (late in the list, most of the time)
    return {
        "question": question,
        **{f"option_{letter.lower()}": option for letter, option in zip(slides.LETTERS, options, strict=False)},
        "answer": slides.LETTERS[options.index(right)],
        "explanation": maybe(0.7, text(PACK, "artefact.explanation", variables)),
    }, {}


def _discovery(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    outlet, headline = text(PACK, "artefact.outlet", variables), text(PACK, "artefact.headline", variables)
    if not outlet or not headline:
        return None
    texts = {
        "outlet": outlet,
        "headline": headline,
        "subheadline": maybe(0.8, text(PACK, "artefact.subheadline", variables)),
    }
    return texts, {"photo": _OBJECT(context)}


# THE GIFT SHOP: the prices on tiles, one big price, or three souvenirs


def _prices(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.5 else 3
    souvenirs = different(PACK, "gift_shop.item", variables, count - 1)
    punchline, title = text(PACK, "gift_shop.item_punchline", variables), text(PACK, "gift_shop.shop_title", variables)
    if not title or not punchline or len(souvenirs) < count - 1:
        return None
    known = words(PACK, "gift_shop.price")  # (the cheapest first)
    prices = [known[index] for index in sorted(random_util.sample(range(len(known)), count - 1))]
    prices.append(random_util.choice(words(PACK, "gift_shop.punchline_price")))
    texts: dict[str, str | None] = {"title": title}
    for index, (price, label) in enumerate(zip(prices, [*souvenirs, punchline], strict=True), 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = price, label
    return texts, behind(context, KPI_PICTURES)


def _one_price(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "gift_shop.big_label", variables)
    if not label:
        return None
    return {
        "title": maybe(0.8, text(PACK, "gift_shop.big_title", variables)),
        "number": random_util.choice(words(PACK, "gift_shop.big_amount")),
        "label": label,
        "source": maybe(0.7, text(PACK, "gift_shop.big_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _souvenirs(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    souvenirs = different(PACK, "gift_shop.souvenir", variables, 2)
    punchline = text(PACK, "gift_shop.souvenir_punchline", variables)
    if len(souvenirs) < 2 or not punchline:
        return None
    texts = {"title": text(PACK, "gift_shop.souvenirs_title", variables), **_items("caption", [*souvenirs, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_SOUVENIR, context, 3), 1)}


# THE SLIDE GENERATORS


def _part(
    part: str,
    weight: float,
    kind: str,
    content: Any,
    tags: list[str],
    name: str,
    recipe: Recipe,
    repeats: int = 2,
) -> SlideGeneratorData:
    """A slide generator of one of the arc's parts: its slides are of the kind, classic ones from the content."""
    return SlideGeneratorData(
        KindSlideGenerator(kind, content),
        weight_function=InPart(ARC, part, weight),
        retries=3,
        allowed_repeated_elements=repeats,
        tags=[part, *tags],
        name=f"{name} (Museum)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a museum's sign or its guide would say it: a few words"
_FEW_WORDS = "in two to five words"
_LABEL = "what the price buys, without the price itself, in a few words"
_PRICE = "the price, with its currency, such as '€45'"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Museum)",
        llm=Recipe("title"),
    ),
    # The welcome
    _part(
        "welcome",
        1.3,
        "full_image",
        _welcome,
        ["full_image"],
        "Welcome",
        Recipe(
            "full_image",
            (_HALL,),
            brief="The tour's welcome: the museum's grand hall, filling the slide, under the guide's greeting, which "
            "names the museum",
            hints={"title": "the guide's greeting, which names the museum by a made-up name, in a few words"},
        ),
    ),
    _part(
        "welcome",
        1.1,
        "agenda",
        _house_rules,
        ["agenda"],
        "House Rules",
        Recipe(
            "agenda",
            brief="The museum's house rules, before the tour begins: three or four rules, numbered, the last one the "
            "punchline, an odd rule that only this museum would need",
            hints={
                "title": "the rules' title, such as 'House rules'",
                "items": f"three or four rules, separated by |, each at most {AGENDA_ITEM} characters: the last one "
                "the punchline",
            },
        ),
    ),
    _part(
        "welcome",
        0.8,
        "agenda",
        _tour,
        ["agenda"],
        "The Tour",
        Recipe(
            "agenda",
            brief="The tour's stops, in order: three or four rooms of the museum, the last one the gift shop, or "
            "another punchline",
            hints={
                "title": "the tour's title, such as 'Today's tour'",
                "items": f"three or four stops, separated by |, each at most {AGENDA_ITEM} characters: the last one "
                "the punchline",
            },
        ),
    ),
    # The masterpiece
    _part(
        "masterpiece",
        1.3,
        "image",
        _labelled,
        ["single_image", "labelled_painting"],
        "Masterpiece",
        Recipe(
            "image",
            (_PAINTING,),
            brief="The masterpiece of the collection: a painting of the topic, under its museum label, which the guide "
            "admires and explains",
            hints={
                "title": "the painting's label: its grand made-up title about the topic and its year, such as "
                "'Penguin at Dawn, 1642'"
            },
        ),
    ),
    _part(
        "masterpiece",
        1,
        "full_image",
        _full_bleed,
        ["full_image", "full_painting"],
        "Masterpiece in Full",
        Recipe(
            "full_image",
            (_PAINTING,),
            brief="The masterpiece, filling the slide: a painting of the topic, under its grand made-up title, for the "
            "group to take in",
            hints={"title": "the painting's grand made-up title about the topic, or a word on what to look at in it"},
        ),
    ),
    _part(
        "masterpiece",
        1.1,
        "two_columns",
        _restoration,
        ["two_captions"],
        "The Restoration",
        Recipe(
            "two_columns",
            (_PAINTING, _RESTORED),
            brief="The masterpiece before and after its restoration, side by side: the old painting, and a clumsy "
            "drawing of the same thing, as a restoration that went wrong left it; the guide is very proud of it",
            hints={
                "title": "a title about the restoration, or empty for none",
                "caption_1": f"the painting before its restoration, {_FEW_WORDS}",
                "caption_2": f"the painting after its restoration, {_FEW_WORDS}, as if it went well",
            },
        ),
    ),
    # The artist
    _part(
        "artist",
        1.3,
        "timeline",
        _life,
        ["timeline", "diagram", "history"],
        "The Artist's Life",
        Recipe(
            "timeline",
            brief="The life of the artist, a made-up old master (never a real artist), as a timeline, oldest first: "
            "from their birth to their obsession with the topic, the last moment the punchline",
            hints={
                "title": "the timeline's title, which names the artist by their made-up name",
                **{f"event_{index}": f"what happened in the artist's life then, {_FEW_WORDS}" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"date_5", "event_5"}), "with four moments"),
                Variant(1, note="with five moments"),
            ),
        ),
    ),
    _part(
        "artist",
        1,
        "fun_fact",
        _artist_fact,
        ["fun_fact"],
        "The Artist's Secret",
        Recipe(
            "fun_fact",
            (_ARTWORK,),
            brief="A fun fact about the artist, a made-up old master (never a real artist): an odd habit or a "
            "scandal, about the topic, stated as certain, beside one of their works",
            hints={
                "fact": "the fact about the artist, by their made-up name: one sentence, stated as certain",
                "source": "a made-up, unreliable source, such as the museum's audio guide",
            },
            facts=False,
        ),
    ),
    _part(
        "artist",
        0.8,
        "social_post",
        _artist_post,
        ["social_post"],
        "The Artist's Post",
        Recipe(
            "social_post",
            (_ARTWORK,),
            brief="A post by the artist, a made-up old master (never a real artist), as if they had social media "
            "centuries ago: their frustrations with painting the topic, beside one of their works",
            hints={
                "title": "a title such as 'From the artist's diary', or empty for none",
                "author": "the artist's made-up name, as an old master's",
                "text": "the post: what the artist wrote, in the voice of an old master, about the topic",
            },
        ),
        repeats=1,
    ),
    # The eras
    _part(
        "eras",
        1.3,
        "three_columns",
        _periods,
        ["three_captions"],
        "Three Periods",
        Recipe(
            "three_columns",
            (_ARTWORK, _ARTWORK, _ARTWORK),
            brief="Three periods of the artist, or of the topic in art, each a work of art with its period's name, "
            "the last one the punchline",
            hints={
                "title": "a title about the periods, or empty for none",
                "caption_1": f"the first period's name, {_FEW_WORDS}",
                "caption_2": f"the second period's name, {_FEW_WORDS}",
                "caption_3": f"the last period's name, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "eras",
        1,
        "tier_list",
        _movements,
        ["tier_list"],
        "The Movements, Ranked",
        Recipe(
            "tier_list",
            brief="The art movements, ranked by the guide in a tier list: real ones and made-up ones, with the "
            "topic's own movement in the S tier, the punchline",
            hints={
                "title": "the tier list's title, such as 'Art movements, ranked'",
                "s_tier": "the topic's own art movement, named after it, such as 'Penguinism': the punchline",
            },
        ),
    ),
    _part(
        "eras",
        0.9,
        "pyramid",
        _hierarchy,
        ["pyramid", "diagram"],
        "The Hierarchy of Art",
        Recipe(
            "pyramid",
            brief="The hierarchy of art as a pyramid, as the guide sees it: the topic at the very top, the punchline, "
            "and the humblest art there is at the base",
            hints={"title": "the pyramid's title, such as 'The hierarchy of art'"},
        ),
    ),
    # The artefact
    _part(
        "artefact",
        1.3,
        "image",
        _artefact,
        ["single_image"],
        "Artefact",
        Recipe(
            "image",
            (_OBJECT,),
            brief="An artefact behind glass: an odd object to do with the topic, under its museum label, which says "
            "what nobody knows about it",
            hints={"title": "the artefact's label: its number and what it might be, such as 'Exhibit 12: use unknown'"},
        ),
    ),
    _part(
        "artefact",
        1,
        "quiz",
        _what_for,
        ["quiz"],
        "What Was It For",
        Recipe(
            "quiz",
            brief="A quiz for the group on what people once used the topic for: three or four odd uses, and the "
            "museum's own answer, the punchline, which is the right one",
            hints={"explanation": "the museum's reason for its answer, without naming any of the options"},
            facts=False,
        ),
    ),
    _part(
        "artefact",
        0.8,
        "news_headline",
        _discovery,
        ["news"],
        "The Discovery",
        Recipe(
            "news_headline",
            (_OBJECT,),
            brief="The news of the artefact's discovery, as an art paper or the evening news had it: where an odd "
            "object to do with the topic was found, and what the experts make of it",
            hints={"outlet": "the made-up name of an art paper or a news channel"},
        ),
        repeats=1,
    ),
    # The gift shop
    _part(
        "gift_shop",
        1.3,
        "kpi",
        _prices,
        ["kpi"],
        "Gift Shop Prices",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The gift shop's prices, on tiles, as the tour ends: souvenirs of the topic and what they cost, from "
            "the cheapest to the last one, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The gift shop'",
                **{f"number_{index}": _PRICE for index in range(1, 5)},
                **{f"label_{index}": _LABEL for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three souvenirs"),
                    Variant(1, note="with four souvenirs"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    _part(
        "gift_shop",
        1,
        "big_number",
        _one_price,
        ["big_number"],
        "Gift Shop Special",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The gift shop's special, as one big price: far too much for a small souvenir of the topic",
            hints={
                "title": _TITLE_HINT + ", such as 'In the gift shop'",
                "number": _PRICE,
                "label": "what the price buys, without the price itself: a small souvenir of the topic",
                "source": "the small print, such as 'Members get 5% off'",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "gift_shop",
        0.9,
        "three_columns",
        _souvenirs,
        ["three_captions"],
        "Souvenirs",
        Recipe(
            "three_columns",
            (_SOUVENIR, _SOUVENIR, _SOUVENIR),
            brief="Three souvenirs of the topic from the gift shop, each a photo with a caption, the last one the "
            "punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Take it home'",
                "caption_1": f"a souvenir, {_FEW_WORDS}",
                "caption_2": f"another souvenir, {_FEW_WORDS}",
                "caption_3": f"the last souvenir, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
]

# The format's other slides, for the free slides between the parts (and to stand in for a part's slide that none of
# the part's generators can make): memes most of all (D63), full-screen pictures and deep questions over photos,
# which a talk may have any number of (so that the free slides of a long tour, without fair use too, never run out of
# slides), gifs, quotes, the museum's reviews, a dare for the group and an alignment chart
_OTHERS: Final = {
    "Meme": 2,
    "Full Screen Neutral Images": 1,
    "Full Screen Pixabay Deep": 0.9,
    "Full Screen Gif": 0.8,
    "Quote": 0.6,
    "Reviews": 0.7,
    "Dare": 0.4,
    "Alignment Chart": 0.4,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Museum)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 1.2, _variables, "Museum", "as a museum's guide or its signs would whisper it"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a tour may have (see presentation_schema.most_slides): each kind once, so that a part of two
# slides has two kinds (a masterpiece under its label and full-bleed are of kinds of their own here, labelled_painting
# and full_painting); two single images, for the masterpiece and the artefact; full-bleed photos aren't capped, as the
# TED-like talks' aren't; and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 1,
    "single_image": 2,
    "labelled_painting": 1,
    "full_painting": 1,
    "two_captions": 1,
    "three_captions": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
