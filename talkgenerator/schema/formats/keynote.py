"""The product keynote (docs/v5-plan.md, section 7; D59): a product made of the talk's topic, launched on a big stage
as tech companies launch theirs.

Its arc goes from a big opening statement (over a photo, as one number, or as a full-bleed photo with a greeting)
through the one idea (a bold question, or a Venn diagram with the product where it all meets), the reveal (the product
in one photo, a picture that prefers to be generated, or full-bleed), its features (three photos, specs on tiles, or a
chart it wins by far), a live demo (that crashes, as a fake error message, how it works in a few steps, or a photo that
the presenter has to present as the demo) and the price (a big number, the models' prices on tiles, or when it ships)
to the "one more thing" (said over a photo, or a second product, revealed full-bleed) and a closing line (over a photo,
full-bleed, or someone's post about the keynote), before its closer says the product is "Available today" (D76),
outside the keynote's slides. A short keynote keeps the opening, the reveal, a feature and the one
more thing; a long one gives the features a second slide, and its free slides (a slide of ten at least, D63) are deep
questions over photos, memes, gifs, its own provocations ("Revolutionary.", over a full-screen picture), quotes, the
press and early reviews. The product's made-up name comes from the topic (see
talkgenerator.schema.formats.product), so that a classic keynote's slides name the product its title launches.

A startup founder gives a keynote more often than the other personas, a motivational speaker almost as often, and an
influencer and a time traveller a little more often; its themes are dark minimal ones more often, and clean keynotes.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, product_line, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import ERROR_BUTTON, Recipe, Variant, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    different,
    maybe,
    photos,
    product,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.util import random_util

PACK: Final = "keynote"

ARC: Final = Arc(
    (
        Part("opening", rank=2),
        Part("idea", rank=5),
        Part("reveal", rank=0),
        Part("features", 1, 2, rank=3),
        Part("demo", rank=4),
        Part("price", rank=6),
        Part("one_more_thing", rank=1),
        Part("closing", rank=7),
    ),
    free=0.15,  # (D63: a slide of ten for a meme, a gif or a picture, as in the other formats)
)

KEYNOTE: Final = Format(
    brief="a product keynote on a big stage, as tech companies launch their products: a big opening statement, the "
    "one idea, the reveal of the product, its features, a live demo, the price, the 'one more thing' and a closing "
    "line. The topic is the product, however absurd, and every slide is a keynote's, played straight: few words, "
    "huge type and big photos",
    title_hint="like a product keynote's title: the product's made-up name and a grand promise, in a few words",
    job_hint="their role at the company launching the product, as a keynote introduces them",
    # (×7 and ×5, from ×5 and ×3.5, since D79 brought the personas to 21)
    personas={
        "startup_founder": 7,
        "motivational_speaker": 5,
        "influencer": 1.5,
        "time_traveller": 1.2,
        "infomercial_host": 1.3,
        "game_show_host": 1.3,
    },
    themes={
        "dark minimal": 5,
        "clean keynote": 2.5,
        "neon": 1.3,
        "Swiss poster": 1.2,
        "vintage paper": 0.4,
        "chalkboard": 0.4,
        "kids": 0.4,
        "academic": 0.4,
        "clip-art corporate": 0.5,
        "newspaper": 0.5,
        "Comic Sans everywhere": 0.5,
        "1997 WordArt": 0.6,
    },
    arc=ARC,
    # (its closer says the product is available today: D76)
    closer=Closer(said("available"), product_line, presenter),
    scene="keynote stage",
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its product's name, the presenter and
    the title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["product"] = product(str(context.get("topic") or context["seed"]))
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE TITLE SLIDE: the product's name and its promise, and who launches it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic keynote's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "product": product(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a dark stage behind the big statements, a striking photo of the topic, the product (a picture that prefers to
# be generated), what its features do, an odd photo for the demo, and the one more thing
_STAGE = cg.statement_backdrop_generator
_HERO = ImageSlot("a big, striking photo of the topic", aesthetic="photo")
# (D63: an absurd invention, searched as a gadget or a machine, or drawn as an advertisement's product shot)
_PRODUCT = ImageSlot(
    "the product a keynote reveals, an absurd invention, shown off as an advertisement would",
    aesthetic="product-shot",
    generate=True,
)
_FEATURE = ImageSlot("a photo of what one of the product's features does", aesthetic="photo")
_DEMO = cg.weird_copyright_free_generator
_THING = ImageSlot("an odd photo of the one more thing", aesthetic="weird-stock", generate=True)
_POST_PHOTO = cg.copyright_free_generator


# THE OPENING: a statement over a photo, one number, or a full-bleed photo with a greeting


def _opening_statement(context: dict[str, Any]) -> Made | None:
    statement = text(PACK, "opening.opening_statement", _variables(context))
    return ({"text": statement}, {"background": _STAGE(context)}) if statement else None


def _opening_number(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "opening.opening_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "opening.opening_number_title", variables),
        "number": random_util.choice(words(PACK, "opening.opening_number")),
        "label": label,
        "source": maybe(0.6, text(PACK, "opening.opening_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _opening_image(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "opening.greeting", _variables(context))
    return ({"title": title}, {"image": _HERO(context)}) if title else None


# THE ONE IDEA: a bold question, or where it all meets


def _idea(context: dict[str, Any]) -> Made | None:
    idea = text(PACK, "idea.idea", _variables(context))
    return ({"text": idea}, {"background": _STAGE(context)}) if idea else None


def _idea_venn(context: dict[str, Any]) -> Made | None:
    """The topic, in one circle, and one or two things that seem to have nothing to do with it, in the others."""
    variables = _variables(context)
    topic = text(PACK, "idea.topic_circle", variables)
    others = different(PACK, "idea.circle", variables, 1 if random_util.random() < 0.6 else 2)
    title = text(PACK, "idea.venn_title", variables)
    if not title or not topic or not others:
        return None
    return {"title": title, **_items("circle", [topic, *others]), "overlap": variables["product"]}, {}


# THE REVEAL: the product, in one photo or full-bleed


def _introducing(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "reveal.reveal_title", _variables(context))
    return ({"title": title}, {"image": _PRODUCT(context)}) if title else None


def _product_shot(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "reveal.shot_title", _variables(context))
    return ({"title": title}, {"image": _PRODUCT(context)}) if title else None


# THE FEATURES: three photos, specs on tiles, or a chart the product wins by far


def _three_features(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    features = different(PACK, "features.feature", variables, 2)
    punchline = text(PACK, "features.feature_punchline", variables)
    if len(features) < 2 or not punchline:
        return None
    texts = {"title": text(PACK, "features.features_title", variables), **_items("caption", [*features, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_FEATURE, context, 3), 1)}


def _specs(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.5 else 3
    specs = [spec.split("|") for spec in different(PACK, "features.spec", variables, count - 1)]
    punchline = (text(PACK, "features.spec_punchline", variables) or "").split("|")
    title = text(PACK, "features.specs_title", variables)
    if not title or len(specs) < count - 1 or len(punchline) != 2 or any(len(spec) != 2 for spec in specs):
        return None
    texts: dict[str, str | None] = {"title": title}
    for index, (number, label) in enumerate([*specs, punchline], 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = number.strip(), label.strip()
    return texts, behind(context, KPI_PICTURES)


def _faster(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    rivals = different(PACK, "features.rival", variables, random_util.randint(2, 3))
    title = text(PACK, "features.bars_title", variables)
    if not title or len(rivals) < 2:
        return None
    return {
        "title": title,
        "bars": " | ".join([*rivals, variables["product"]]),
        "value_axis": maybe(0.8, text(PACK, "features.bars_axis", variables)),
    }, {}


# THE DEMO: it crashes, how it works, or a photo to present as the demo


def _demo_crash(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    buttons = different(PACK, "demo.button", variables, random_util.randint(1, 2))
    punchline, message = text(PACK, "demo.button_punchline", variables), text(PACK, "demo.error", variables)
    if not message or not punchline or not buttons:
        return None
    return {
        "title": maybe(0.8, text(PACK, "demo.error_title", variables)),
        "message": message,
        "code": maybe(0.8, text(PACK, "demo.error_code", variables)),
        "buttons": " | ".join([*buttons, punchline]),
    }, {}


def _how_it_works(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "demo.how_first", variables), text(PACK, "demo.how_last", variables)
    middle = different(PACK, "demo.how_step", variables, count - 2)
    title = text(PACK, "demo.how_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    return {"title": title, **_items("step", [first, *middle, last])}, {}


def _live_demo(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "demo.demo_title", _variables(context))
    return ({"title": title}, {"image": _DEMO(context)}) if title else None


# THE PRICE: one big number, the models on tiles, or when it ships


def _price(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "price.price_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "price.price_title", variables),
        "number": random_util.choice(words(PACK, "price.amount")),
        "label": label,
        "source": maybe(0.8, text(PACK, "price.price_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _models(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.4 else 3
    models = different(PACK, "price.model", variables, count - 1)
    punchline, title = text(PACK, "price.model_punchline", variables), text(PACK, "price.models_title", variables)
    if not title or not punchline or len(models) < count - 1:
        return None
    known = words(PACK, "price.model_price")  # (the cheapest first)
    prices = [known[index] for index in sorted(random_util.sample(range(len(known)), count - 1))]
    prices.append(random_util.choice(words(PACK, "price.punchline_price")))
    texts: dict[str, str | None] = {"title": title}
    for index, (price, label) in enumerate(zip(prices, [*models, punchline], strict=True), 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = price, label
    return texts, behind(context, KPI_PICTURES)


def _availability(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 4)
    steps = different(PACK, "price.available", variables, count - 1)
    punchline, title = text(PACK, "price.available_punchline", variables), text(PACK, "price.when_title", variables)
    if not title or not punchline or len(steps) < count - 1:
        return None
    known = words(PACK, "price.when")  # (soonest first)
    dates = [known[index] for index in sorted(random_util.sample(range(len(known)), count))]
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(dates, [*steps, punchline], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


# ONE MORE THING: said over a photo, or a second product revealed full-bleed


def _one_more_thing(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "more.one_more_thing", _variables(context))
    return ({"text": said}, {"background": _STAGE(context)}) if said else None


def _one_more_reveal(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "more.thing_title", _variables(context))
    return ({"title": title}, {"image": _THING(context)}) if title else None


# THE CLOSING LINE: over a photo, full-bleed, or someone's post about the keynote


def _closing_line(context: dict[str, Any]) -> Made | None:
    line = text(PACK, "closing.closing_line", _variables(context))
    return ({"text": line}, {"background": _STAGE(context)}) if line else None


def _closing_image(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "closing.closing_title", _variables(context))
    return ({"title": title}, {"image": _HERO(context)}) if title else None


def _handle(author: str) -> str:
    first = "".join(letter for letter in author.split()[0].lower() if letter.isalpha()) if author.split() else "fan"
    return random_util.choice((f"{first}_watches_keynotes", f"real{first}", f"{first}{random_util.randint(2, 99)}"))[
        :24
    ]


def _reaction(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "closing.reaction", variables)
    author = cg.full_name_generator({})
    if not post or not author:
        return None
    photo = _POST_PHOTO(context) if random_util.random() < 0.5 else None
    texts = {
        "title": maybe(0.7, text(PACK, "closing.reaction_title", variables)),
        "author": str(author),
        "handle": _handle(str(author)),
        "text": post,
    }
    return texts, {"photo": photo}


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
        name=f"{name} (Keynote)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a keynote's slide has it: a few words"
_FEW_WORDS = "in two to four words"
_HUGE = "in a few words, as a keynote shows them huge"
_LABEL = "what the number measures, without the number itself"
_NUMBER = "the number as people read it, with its unit, such as '2 billion' or '18 h'"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Keynote)",
        llm=Recipe("title"),
    ),
    # The opening
    _part(
        "opening",
        1.3,
        "statement",
        _opening_statement,
        ["statement"],
        "Opening Statement",
        Recipe(
            "statement",
            (_STAGE,),
            brief="The keynote's big opening statement, over a photo: that today, everything changes for the topic",
            hints={"text": f"the opening statement, as one sentence {_HUGE}"},
        ),
    ),
    _part(
        "opening",
        1,
        "big_number",
        _opening_number,
        ["big_number"],
        "Opening Number",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The keynote's opening, as one huge number: how well the company has done since its last keynote",
            hints={
                "title": _TITLE_HINT + ", such as 'Since last year'",
                "number": _NUMBER,
                "label": _LABEL,
                "source": "a made-up, unreliable source, or empty for none",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "opening",
        0.9,
        "full_image",
        _opening_image,
        ["full_image"],
        "Opening Image",
        Recipe(
            "full_image",
            (_HERO,),
            brief="The keynote's opening: a striking photo of the topic, filling the slide, under a greeting",
            hints={"title": f"the greeting, {_HUGE}, such as 'Good morning.'"},
        ),
    ),
    # The one idea
    _part(
        "idea",
        1.2,
        "statement",
        _idea,
        ["statement"],
        "The One Idea",
        Recipe(
            "statement",
            (_STAGE,),
            brief="The keynote's one idea, as a bold question over a photo: what if the topic were completely "
            "different",
            hints={"text": f"the one idea, as a question {_HUGE}"},
        ),
    ),
    _part(
        "idea",
        1,
        "venn",
        _idea_venn,
        ["venn_diagram"],
        "Where It All Meets",
        Recipe(
            "venn",
            brief="The keynote's one idea, as a Venn diagram: the topic and one or two things that seem to have "
            "nothing to do with it, and the product where they all meet, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The idea'",
                "overlap": "the product, by its made-up name",
            },
        ),
    ),
    # The reveal
    _part(
        "reveal",
        1.3,
        "image",
        _introducing,
        ["single_image"],
        "Introducing",
        Recipe(
            "image",
            (_PRODUCT,),
            brief="The reveal: the product, in one photo, under a title that introduces it by its made-up name",
            hints={"title": "a title that introduces the product by its made-up name, such as 'Introducing ...'"},
        ),
    ),
    _part(
        "reveal",
        1,
        "full_image",
        _product_shot,
        ["full_image"],
        "Product Shot",
        Recipe(
            "full_image",
            (_PRODUCT,),
            brief="The reveal: the product, in a photo filling the slide, with its made-up name as the title",
            # (With "such as '... It's here.'", three free models' titles of four said "It's here.")
            hints={"title": "the product's made-up name, and a few words of your own about it"},
        ),
    ),
    # The features
    _part(
        "features",
        1.5,
        "three_columns",
        _three_features,
        ["three_captions"],
        "Three Features",
        Recipe(
            "three_columns",
            (_FEATURE, _FEATURE, _FEATURE),
            brief="Three of the product's features, each a photo of what it does with a caption, the last one the "
            "punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Three things you'll love'",
                "caption_1": f"a feature, {_FEW_WORDS}",
                "caption_2": f"another feature, {_FEW_WORDS}",
                "caption_3": f"the last feature, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "features",
        1.1,
        "kpi",
        _specs,
        ["kpi"],
        "Specs",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The product's specs, as figures on tiles: each a number with its unit and what it measures, the "
            "last one the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Specs'",
                **{
                    f"number_{index}": "the spec's number with its unit, such as '2×' or '18 h'"
                    for index in range(1, 5)
                },
                **{f"label_{index}": _LABEL for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three specs"),
                    Variant(1, note="with four specs"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    _part(
        "features",
        0.9,
        "chart_bars",
        _faster,
        ["bar_chart", "chart"],
        "Faster Than Ever",
        Recipe(
            "chart_bars",
            brief="How much better the product is, as a ranking in bars that it wins by far: what came before it (the "
            "old product, the competition, an odd thing), and the product, the last bar",
            hints={
                "title": "what the ranking compares, as a keynote's chart has it",
                "bars": "two to four things (only their names), separated by |, and the product's made-up name last",
                "value_axis": "the measure, such as 'Speed' or 'Joy'",
            },
        ),
    ),
    # The demo
    _part(
        "demo",
        1.3,
        "error_message",
        _demo_crash,
        ["error_message"],
        "Demo Crash",
        Recipe(
            "error_message",
            brief="The live demo, which crashes: a fake error message from the product, in the middle of the keynote, "
            "with its buttons, the last one the punchline",
            hints={
                "title": "the dialog's title, such as the product's made-up name",
                "buttons": f"two or three buttons, separated by |, each at most {ERROR_BUTTON} characters: the last "
                "one the punchline, such as a way to save the demo",
            },
        ),
    ),
    _part(
        "demo",
        1,
        "process",
        _how_it_works,
        ["process"],
        "How It Works",
        Recipe(
            "process",
            brief="The demo, as how the product works, step by step, the last one the punchline: a step that nobody can "
            "explain, or that gives the game away",
            hints={
                "title": _TITLE_HINT + ", such as 'How it works'",
                **{f"step_{index}": f"a step, {_FEW_WORDS}" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"step_4", "step_5"}), "in three steps"),
                Variant(1, frozenset({"step_5"}), "in three or four steps"),
                Variant(1, note="in three to five steps"),
            ),
        ),
    ),
    _part(
        "demo",
        1.1,
        "full_image",
        _live_demo,
        ["full_image"],
        "Live Demo",
        Recipe(
            "full_image",
            (_DEMO,),
            brief="The live demo: an odd photo, filling the slide, that the presenter has to present as the demo",
            hints={"title": "a title such as 'Live demo'"},
        ),
    ),
    # The price
    _part(
        "price",
        1.3,
        "big_number",
        _price,
        ["big_number"],
        "Price",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The price, as one big number: what the product costs, and what that gets you",
            hints={
                "title": _TITLE_HINT + ", such as 'Pricing'",
                "number": "the price with its currency, such as '$999'",
                "label": "what it gets you, or how to pay it, without the price itself",
                "source": "the small print, such as its colours",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "price",
        1,
        "kpi",
        _models,
        ["kpi"],
        "Models and Prices",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The models and their prices, on tiles: each a price and who the model is for, from the cheapest to "
            "the last one, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Choose yours'",
                **{f"number_{index}": "the model's price, with its currency" for index in range(1, 5)},
                **{f"label_{index}": "the model, and who it's for, without its price" for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three models"),
                    Variant(1, note="with four models"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    _part(
        "price",
        0.8,
        "timeline",
        _availability,
        ["timeline"],
        "Availability",
        Recipe(
            "timeline",
            brief="When the product is available: from pre-orders today, soonest first, to the last moment, the "
            "punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Availability'",
                **{f"event_{index}": f"what happens then, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    # One more thing
    _part(
        "one_more_thing",
        1.2,
        "statement",
        _one_more_thing,
        ["statement"],
        "One More Thing",
        Recipe(
            "statement",
            (_STAGE,),
            brief="The 'one more thing', said over a photo, just as the keynote seems over: the presenter has to say "
            "what the thing is",
            hints={"text": "the words that announce one more thing, and nothing more"},
        ),
    ),
    _part(
        "one_more_thing",
        1.2,
        "full_image",
        _one_more_reveal,
        ["full_image"],
        "One More Thing Reveal",
        Recipe(
            "full_image",
            (_THING,),
            brief="The 'one more thing': a second, stranger product, revealed in an odd photo filling the slide",
            # (A free model named the second product "One More Thing")
            hints={"title": "'One more thing:' and then the second product, by a made-up name of its own"},
        ),
    ),
    # The closing line
    _part(
        "closing",
        1.2,
        "statement",
        _closing_line,
        ["statement"],
        "Closing Line",
        Recipe(
            "statement",
            (_STAGE,),
            brief="The keynote's closing line, over a photo: the product, and what it means for the world",
            hints={"text": f"the closing line, {_HUGE}"},
        ),
    ),
    _part(
        "closing",
        1,
        "full_image",
        _closing_image,
        ["full_image"],
        "Closing Image",
        Recipe(
            "full_image",
            (_HERO,),
            brief="The keynote's closing: a striking photo of the topic, filling the slide, under its last words",
            hints={"title": f"the last words, {_HUGE}, such as 'Thank you.'"},
        ),
    ),
    _part(
        "closing",
        0.6,
        "social_post",
        _reaction,
        ["social_post"],
        "Audience Reaction",
        Recipe(
            "social_post",
            (_POST_PHOTO,),
            brief="Someone's post about the keynote, as it ends: thrilled, or thrilled about the wrong thing",
            hints={"title": "a title such as 'What people are saying', or empty for none"},
        ),
        repeats=1,
    ),
]

# The format's other slides, for a long keynote's free slides (and to stand in for a part's slide that none of the
# part's generators can make): deep questions and full-screen photos, which a talk may have any number of (so that the
# free slides of a long one, without fair use too, never run out of slides), quotes, gifs, memes, the press, early
# reviews, a fun fact and a dare
_OTHERS: Final = {
    "Full Screen Pixabay Deep": 1.2,
    "Full Screen Neutral Images": 0.8,
    "Meme": 1.6,  # (D63: memes more often, as in the other formats)
    "Full Screen Gif": 0.9,
    "News Headline": 0.7,
    "Reviews": 0.7,
    "Quote": 0.6,
    "Fun Fact": 0.5,
    "Dare": 0.5,
    "Tier List": 0.4,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Keynote)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 1.2, _variables, "Keynote", "as a keynote announces a product"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a keynote may have (see presentation_schema.most_slides): each kind once, but for the big
# statements, as many as its opening, its idea, its one more thing and its closing line may have (full-bleed photos
# aren't capped, as the TED-like talks' aren't), and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 3,
    "single_image": 1,
    "three_captions": 1,
    "process": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
