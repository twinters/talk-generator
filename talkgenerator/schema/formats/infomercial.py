"""The late-night TV infomercial (docs/v5-plan.md, section 7; D79): a gadget made of the talk's topic, sold on
television as infomercials sell theirs, played straight and over the top.

Its arc goes from the everyday problem (a problem slide, "Tired of this?", or someone failing at it in a full-bleed
photo under "There has to be a better way!") through the gadget (in one photo, a picture that prefers to be generated,
or full-bleed: "As seen on TV!"), its demonstration (three photos of all it does, the last one something no gadget
should do; how it works in a few easy steps; or the old way and the gadget's way, side by side), testimonials (five-star
reviews, the last one glowing about the wrong thing; a happy customer's post; or before and after), the fine print (a
wall of absurd disclaimers, or terms whose every button agrees), the price (prices that drop tile by tile to today's, or
one big price in easy payments) and "But wait, there's more!" (a free bonus, full-bleed; twice the offer as one big
number; or the words alone, for the presenter to say what more there is) to the call to order now (over a photo of
operators standing by, a big made-up phone number, or the whole audience ordering at once), before its closer says "Call
now!" once more, its operators standing by (D76), outside its slides. A short infomercial keeps the problem, the gadget,
its demonstration and "But wait"; a quarter of its slides are free (D63), for memes, gifs, full-screen pictures, its own
provocations ("As seen on TV!", over a full-screen picture), the press, a fun fact, a quiz and the like, and its fine
print comes in talks of eleven slides or more. The gadget's made-up name comes from the topic (see
talkgenerator.schema.formats.gadget), so that a classic infomercial's slides sell the gadget its title names.

An infomercial host presents an infomercial far more often than the other personas, a motivational speaker and a
game-show host a little more often, a startup founder and an influencer too; its themes are the loud families more often
(1997 WordArt, neon, Comic Sans everywhere), and the quiet ones less.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import ERROR_BUTTON, Recipe, Variant, pictured, problem_variants
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    Made,
    behind,
    big_number,
    different,
    error_dialog,
    gadget,
    maybe,
    one_text,
    part_slide,
    photos,
    problem,
    provocation,
    steps,
    text,
    three_captions,
    title_slide,
    variables_of,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.util import random_util

PACK: Final = "infomercial"

# (D63: a quarter of its slides are free, for memes, gifs and pictures, and its fine print, a wall of text, waits for a
# talk of eleven slides or more)
ARC: Final = Arc(
    (
        Part("problem", rank=2),
        Part("product", rank=0),
        Part("demo", 1, 2, rank=3),
        Part("testimonials", rank=4),
        Part("fine_print", rank=7),
        Part("price", rank=5),
        Part("but_wait", rank=1),
        Part("call_now", rank=6),
    ),
    free=0.25,
)

INFOMERCIAL: Final = Format(
    brief="a late-night TV infomercial for a gadget made of the topic, played straight and over the top: the everyday "
    "problem, the gadget, its demonstration, testimonials, the fine print, the price, 'But wait, there's more!' and "
    "the call to order now. The topic is what the gadget is for, however absurd, and every slide shouts, with "
    "exclamation marks, big prices and before-and-after photos",
    title_hint="like an infomercial's: the gadget's made-up name and a promise, with an exclamation mark",
    job_hint="their part in the infomercial (its host, the gadget's inventor, a satisfied customer), as the screen "
    "introduces them",
    personas={
        "infomercial_host": 9,
        "motivational_speaker": 2,
        "game_show_host": 2,
        "startup_founder": 1.5,
        "influencer": 1.5,
    },
    themes={
        "Y2K": 1.5,
        "70s retro": 1.5,
        "1997 WordArt": 4,
        "neon": 2.5,
        "Comic Sans everywhere": 2,
        "clip-art corporate": 1.5,
        "startup": 1.3,
        "academic": 0.4,
        "vintage paper": 0.5,
        "dark minimal": 0.5,
        "chalkboard": 0.5,
        "blueprint": 0.6,
    },
    arc=ARC,
    # (its closer calls the room to order now, with its operators standing by: D76)
    closer=Closer(said("call_now"), said("standing_by"), presenter),
    scene="tv shopping",
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its gadget's name, the presenter and the
    title."""
    return variables_of(context, gadget=gadget)


# THE TITLE SLIDE: the gadget's name and its promise, and who sells it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic infomercial's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "gadget": gadget(str(context["seed"]))})


# Images: a calm backdrop behind a statement, someone failing at something everyday (generated, in a talk that
# generates pictures), the gadget (a picture that prefers to be generated, as a pitch's product), what it does, the old
# way and the new, before and after, the photo a happy customer posted, the free bonus, and the operators standing by
_BACKDROP = cg.statement_backdrop_generator
_FAIL = ImageSlot(
    "someone failing at something everyday, as an infomercial's problem scene shows it",
    aesthetic="weird-stock",
    generate=True,
)
_GADGET = ImageSlot(
    "the gadget an infomercial sells, an absurd invention, shown off as an advertisement would",
    aesthetic="product-shot",
    generate=True,
)
_DOES = ImageSlot("a photo of what the gadget does, as an infomercial demonstrates it", aesthetic="weird-stock")
_OLD_WAY = ImageSlot("the old way: someone struggling without the gadget", aesthetic="weird-stock")
_NEW_WAY = ImageSlot("the new way: someone delighted, with the gadget", queries=("happy {}", "{}"), aesthetic="photo")
_BEFORE = cg.copyright_free_generator
_AFTER = cg.weird_copyright_free_generator
_POST_PHOTO = cg.copyright_free_generator
_BONUS = ImageSlot("the odd bonus an infomercial throws in for free", aesthetic="weird-stock", generate=True)
_OPERATORS = ImageSlot(
    "a call centre, its operators standing by, behind the slide's text",
    queries=("call center", "telephone operator", "{}"),
    aesthetic="calm-backdrop",
    backups=("photo",),
)


# THE PROBLEM: the problem slide most of the time (D69), or someone failing at it, full-bleed


# (an everyday frustration and a real one, a how-to people look up, more often than the other angles: an
# infomercial's problems are everyone's)
_ANGLES: Final = {"everyday": 1.4, "real": 1.3}
_PROBLEMS: Final = {
    "kicker": "problem.kicker",
    "weird": "problem.weird",
    "everyday": "problem.everyday",
    "crossed": "problem.crossed",
    "typical": "problem.typical",
    "real": "problem.real",
}


def _problem(context: dict[str, Any]) -> Made | None:
    return problem(PACK, _PROBLEMS, _variables(context), context, (_BACKDROP, _FAIL), _ANGLES)


_better_way = one_text(PACK, _variables, "problem.better_way", "title", image=_FAIL)


# THE GADGET: in one photo, or full-bleed
_introducing = one_text(PACK, _variables, "product.introducing", "title", image=_GADGET)
_as_seen_on_tv = one_text(PACK, _variables, "product.as_seen", "title", image=_GADGET)


# THE DEMONSTRATION: three photos of all it does, how it works, or the old way and the new
_it_does_it_all = three_captions(
    PACK, _variables, "demo.features_title", "demo.feature", "demo.feature_punchline", _DOES
)
_how_it_works = steps(PACK, _variables, "demo.how_title", "demo.how_first", "demo.how_step", "demo.how_last")


def _old_way_new_way(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    old, new = text(PACK, "demo.old_way", variables), text(PACK, "demo.new_way", variables)
    if not old or not new:
        return None
    texts = {"title": maybe(0.7, text(PACK, "demo.ways_title", variables)), "caption_1": old, "caption_2": new}
    struggling = _OLD_WAY(context)
    return texts, {"image_1": struggling, "image_2": photos(_NEW_WAY, context, 1, avoid=[struggling])[0]}


# TESTIMONIALS: five-star reviews, a happy customer's post, or before and after


def _testimonials(context: dict[str, Any]) -> Made | None:
    """Two or three reviews, every one of five stars (an infomercial shows no other), the last one glowing about
    something the gadget should never have done."""
    variables = _variables(context)
    count = 3 if random_util.random() < 0.7 else 2
    praise = different(PACK, "testimonials.review", variables, count - 1)
    punchline = text(PACK, "testimonials.review_punchline", variables)
    reviewers = different(PACK, "testimonials.reviewer", variables, count)
    if len(praise) < count - 1 or not punchline or len(reviewers) < count:
        return None
    texts: dict[str, str | None] = {"title": maybe(0.8, text(PACK, "testimonials.reviews_title", variables))}
    for index, (review, reviewer) in enumerate(zip([*praise, punchline], reviewers, strict=True), 1):
        texts[f"stars_{index}"], texts[f"review_{index}"], texts[f"reviewer_{index}"] = "5", review, reviewer
    return texts, {}


def _handle(author: str) -> str:
    first = "".join(letter for letter in author.split()[0].lower() if letter.isalpha()) if author.split() else "fan"
    return random_util.choice((f"{first}_loves_gadgets", f"happy{first}", f"{first}{random_util.randint(2, 99)}"))[:24]


def _happy_customer(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "testimonials.post", variables)
    author = cg.full_name_generator({})
    if not post or not author:
        return None
    photo = _POST_PHOTO(context) if random_util.random() < 0.6 else None
    texts = {
        "title": maybe(0.7, text(PACK, "testimonials.post_title", variables)),
        "author": str(author),
        "handle": _handle(str(author)),
        "text": post,
    }
    return texts, {"photo": photo}


def _before_and_after(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    captions = (text(PACK, "testimonials.before_after", variables) or "").split("|")
    title = text(PACK, "testimonials.results_title", variables)
    if len(captions) != 2 or not title:
        return None
    before = _BEFORE(context)
    texts = {"title": title, "caption_1": captions[0].strip(), "caption_2": captions[1].strip()}
    return texts, {"image_1": before, "image_2": photos(_AFTER, context, 1, avoid=[before])[0]}


# THE FINE PRINT: a wall of disclaimers, or terms whose every button agrees


def _terms(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    points = different(PACK, "fine_print.disclaimer", variables, random_util.randint(11, 14))
    highlight, title = text(PACK, "fine_print.highlight", variables), text(PACK, "fine_print.terms_title", variables)
    if not title or not highlight or len(points) < 5:
        return None
    return {"title": title, "points": " | ".join(points), "highlight": highlight}, {}


_terms_dialog = error_dialog(
    PACK,
    _variables,
    "fine_print.dialog_title",
    "fine_print.clause",
    "fine_print.clause_code",
    "fine_print.agree",
    "fine_print.agree_punchline",
)


# THE PRICE: prices that drop tile by tile, or one big price


def _price_drop(context: dict[str, Any]) -> Made | None:
    """The prices it might have had, dearer first, each with what it would have been (in their order), and today's,
    the punchline."""
    variables = _variables(context)
    count = 4 if random_util.random() < 0.6 else 3
    punchline, title = text(PACK, "price.today_label", variables), text(PACK, "price.drop_title", variables)
    if not title or not punchline:
        return None
    known, labels = words(PACK, "price.was_price"), words(PACK, "price.was_label")  # (the dearest first)
    prices = [known[index] for index in sorted(random_util.sample(range(len(known)), count - 1))]
    stories = [labels[index] for index in sorted(random_util.sample(range(len(labels)), count - 1))]
    prices.append(random_util.choice(words(PACK, "price.today_price")))
    texts: dict[str, str | None] = {"title": title}
    for index, (price, label) in enumerate(zip(prices, [*stories, punchline], strict=True), 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = price, label
    return texts, behind(context, KPI_PICTURES)


_big_price = big_number(
    PACK, _variables, "price.big_title", "price.big_price", "price.big_label", "price.big_source", 0.8
)


# BUT WAIT, THERE'S MORE: a free bonus, twice the offer, or the words alone
_bonus = one_text(PACK, _variables, "but_wait.bonus_title", "title", image=_BONUS)
_double = big_number(
    PACK,
    _variables,
    "but_wait.double_title",
    "but_wait.double_number",
    "but_wait.double_label",
    "but_wait.double_source",
    0.7,
)
_theres_more = one_text(PACK, _variables, "but_wait.more", "text", background=_BACKDROP)


# THE CALL TO ORDER NOW: over a photo of the operators, a big phone number, or the audience ordering at once
_call_now = one_text(PACK, _variables, "call_now.call_now", "text", background=_OPERATORS)
_phone_number = big_number(
    PACK,
    _variables,
    "call_now.phone_title",
    "call_now.phone_number",
    "call_now.phone_label",
    "call_now.phone_source",
    0.8,
)
_order_now = one_text(PACK, _variables, "call_now.order", "audience")


# THE SLIDE GENERATORS


_part = partial(part_slide, ARC, "Infomercial")


_TITLE_HINT = "the slide's title, as an infomercial shouts it: a few words, with an exclamation mark"
_FEW_WORDS = "in two to five words"
_SHOUTED = "in a few words, with an exclamation mark"
_SMALL_PRINT = "the small print, such as shipping and handling, or empty for none"
_PRICED = pictured((), "background", BIG_NUMBER_PICTURES)

_GENERATORS: Final = [
    title_slide(PACK, title_generator, _variables, "Infomercial"),
    # The problem
    # (D69: the problem slide, an infomercial's "Tired of this?", most of the time)
    _part(
        "problem",
        3,
        "problem",
        _problem,
        ["problem_slide"],
        "Problem",
        Recipe(
            "problem",
            (_BACKDROP, _FAIL),
            brief="The everyday problem the gadget solves, as an infomercial opens on it: a small frustration with the "
            "concept that everyone has, made into a disaster",
            hints={
                "kicker": "a short heading over the problem, as an infomercial asks it, such as 'Tired of this?' or "
                "'Sound familiar?'",
                "detail": "a short line under it, a few words, that makes it worse: how often it happens, or to how "
                "many people; it appears on a click",
            },
            variants=problem_variants(_ANGLES),
        ),
    ),
    _part(
        "problem",
        1.5,
        "full_image",
        _better_way,
        ["full_image"],
        "There Has to Be a Better Way",
        Recipe(
            "full_image",
            (_FAIL,),
            brief="The everyday problem the gadget solves, as an infomercial shows it: someone failing at something "
            "everyday with the concept, in a photo filling the slide",
            hints={"title": f"the infomercial's cry for a better way, {_SHOUTED}"},
        ),
    ),
    # The gadget
    _part(
        "product",
        1.3,
        "image",
        _introducing,
        ["single_image"],
        "Introducing",
        Recipe(
            "image",
            (_GADGET,),
            brief="The gadget, revealed in one photo, under a title that introduces it by its made-up name, as an "
            "infomercial does",
            hints={"title": "a title that introduces the gadget by its made-up name, with an exclamation mark"},
        ),
    ),
    _part(
        "product",
        1,
        "full_image",
        _as_seen_on_tv,
        ["full_image"],
        "As Seen on TV",
        Recipe(
            "full_image",
            (_GADGET,),
            brief="The gadget, in a photo filling the slide, under its made-up name and a promise",
            hints={"title": "the gadget's made-up name and a few words of promise, with an exclamation mark"},
        ),
    ),
    # The demonstration
    _part(
        "demo",
        1.5,
        "three_columns",
        _it_does_it_all,
        ["three_captions"],
        "It Does It All",
        Recipe(
            "three_columns",
            (_DOES, _DOES, _DOES),
            brief="What the gadget does, as an infomercial demonstrates it: three photos, each under a caption that "
            "shouts what it does, the last one the punchline, something no gadget should do",
            hints={
                "title": _TITLE_HINT + ", such as 'Watch this!'",
                "caption_1": f"what it does, {_FEW_WORDS}, with an exclamation mark",
                "caption_2": f"something else it does, {_FEW_WORDS}, with an exclamation mark",
                "caption_3": f"the punchline: something no gadget should do, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "demo",
        0.7,
        "process",
        _how_it_works,
        ["process"],
        "How It Works",
        Recipe(
            "process",
            brief="How the gadget works, in a few easy steps, the last one the punchline: what life is like once you "
            "own one",
            hints={
                "title": _TITLE_HINT + ", such as 'Easy as 1, 2, 3!'",
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
        1.2,
        "two_columns",
        _old_way_new_way,
        ["two_captions"],
        "Old Way, New Way",
        Recipe(
            "two_columns",
            (_OLD_WAY, _NEW_WAY),
            brief="The old way and the gadget's way, side by side: someone struggling with the concept, and someone "
            "delighted with the gadget",
            hints={
                "title": "a title that shouts the difference, or empty for none",
                "caption_1": "the old way, in a few words",
                "caption_2": "the gadget's way, by its made-up name, with an exclamation mark",
            },
        ),
    ),
    # The testimonials
    _part(
        "testimonials",
        1.3,
        "reviews",
        _testimonials,
        ["reviews"],
        "Testimonials",
        Recipe(
            "reviews",
            brief="Testimonials of satisfied customers, as five-star reviews: glowing ones, and the last one, the "
            "punchline, glowing about something the gadget should never have done",
            hints={
                "title": "a title such as 'Real customers!', or empty for none",
                **{f"stars_{index}": "5, as every testimonial here gives" for index in range(1, 4)},
                **{
                    f"reviewer_{index}": "a made-up first name and an age or a detail, as an infomercial captions them"
                    for index in range(1, 4)
                },
            },
        ),
    ),
    _part(
        "testimonials",
        0.8,
        "social_post",
        _happy_customer,
        ["social_post"],
        "Happy Customer",
        Recipe(
            "social_post",
            (_POST_PHOTO,),
            brief="A happy customer's post about the gadget, far too enthusiastic, about something it shouldn't do",
            hints={"title": "a title such as 'Our customers love it!', or empty for none"},
        ),
        repeats=1,
    ),
    _part(
        "testimonials",
        1.3,
        "two_columns",
        _before_and_after,
        ["two_captions"],
        "Before and After",
        Recipe(
            "two_columns",
            (_BEFORE, _AFTER),
            brief="Before and after the gadget, side by side: a photo of life with the concept before it, an odd one "
            "after, under a title that promises results",
            hints={
                "title": "a title that promises results, with an exclamation mark",
                "caption_1": "before, in a few words",
                "caption_2": "after, in a few words: the punchline",
            },
        ),
    ),
    # The fine print
    _part(
        "fine_print",
        1,
        "wall_of_text",
        _terms,
        ["wall_of_text"],
        "Terms and Conditions",
        Recipe(
            "wall_of_text",
            brief="The fine print, as a wall of text that nobody can read: dense disclaimers about the gadget, in "
            "legalese, and one absurd one hidden among them, the punchline",
            hints={"title": "a title such as 'Terms and conditions'"},
        ),
        repeats=3,
    ),
    _part(
        "fine_print",
        1,
        "error_message",
        _terms_dialog,
        ["error_message"],
        "Terms Dialog",
        Recipe(
            "error_message",
            brief="The terms and conditions, as a dialog everyone must accept before ordering: one absurd clause about "
            "the gadget, and buttons that all agree, the last one the punchline",
            hints={
                "title": "the dialog's title, such as 'Terms and conditions'",
                "message": "one absurd clause of the fine print, about the gadget",
                "code": "the clause's number, absurdly precise",
                "buttons": f"two or three buttons, separated by |, each at most {ERROR_BUTTON} characters, every one "
                "of them agreeing: the last one the punchline",
            },
        ),
    ),
    # The price
    _part(
        "price",
        1.2,
        "kpi",
        _price_drop,
        ["kpi"],
        "Price Drop",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The price, as an infomercial reveals it: prices on tiles, each lower than the one before, with what "
            "that price would have been, the last one today's price, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'How much would you pay?'",
                **{f"number_{index}": "a price with its currency, lower than the one before" for index in range(1, 5)},
                **{f"label_{index}": "what that price would have been, such as in stores" for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three prices"),
                    Variant(1, note="with four prices"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    _part(
        "price",
        1,
        "big_number",
        _big_price,
        ["big_number"],
        "Easy Payments",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The price, as one big number, in easy payments: what the gadget costs today, and what that gets you",
            hints={
                "title": _TITLE_HINT + ", such as 'Only'",
                "number": "the price with its currency, or as payments, such as '3 × $19.99'",
                "label": "what you get for it, or how to pay it, without the price itself",
                "source": _SMALL_PRINT,
            },
            variants=_PRICED,
        ),
        repeats=3,
    ),
    # But wait, there's more
    _part(
        "but_wait",
        1.4,
        "full_image",
        _bonus,
        ["full_image"],
        "But Wait",
        Recipe(
            "full_image",
            (_BONUS,),
            brief="But wait, there's more: an odd bonus that comes with the gadget, free, in a photo filling the slide",
            hints={"title": f"'But wait!' and the bonus you get free if you order now, {_SHOUTED}"},
        ),
    ),
    _part(
        "but_wait",
        1,
        "big_number",
        _double,
        ["big_number"],
        "Double the Offer",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="But wait, there's more: the offer doubled, as one big number, for anyone who orders in the next "
            "few minutes",
            hints={
                "title": _TITLE_HINT + ", such as 'But wait!'",
                "number": "how much more you get, such as '2 for 1' or '×2'",
                "label": "what you get, and the catch, without the number itself",
                "source": _SMALL_PRINT,
            },
            variants=_PRICED,
        ),
        repeats=3,
    ),
    _part(
        "but_wait",
        0.7,
        "statement",
        _theres_more,
        ["statement"],
        "There's More",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="'But wait, there's more!', said over a photo, and nothing else: the presenter has to say what more "
            "there is",
            hints={"text": "the words that announce there's more, and nothing more"},
        ),
    ),
    # The call to order now
    _part(
        "call_now",
        1.2,
        "statement",
        _call_now,
        ["statement"],
        "Call Now",
        Recipe(
            "statement",
            (_OPERATORS,),
            brief="The call to order now, over a photo of operators standing by",
            hints={"text": "the call to order now, shouted, in a sentence or two"},
        ),
    ),
    _part(
        "call_now",
        1,
        "big_number",
        _phone_number,
        ["big_number"],
        "Phone Number",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The number to call, as one big number: a made-up phone number, and why to call it right now",
            hints={
                "title": _TITLE_HINT + ", such as 'Call now!'",
                "number": "a made-up phone number of the 555 kind, such as '555-0199'",
                "label": "why to call right now, without the number itself",
                "source": "the small print, such as when the lines close, or empty for none",
            },
            variants=_PRICED,
        ),
        repeats=3,
    ),
    _part(
        "call_now",
        1,
        "dare",
        _order_now,
        ["dare"],
        "Order Now",
        Recipe(
            "dare",
            brief="The call to order now, as audience participation: the whole room orders the gadget at once",
            hints={
                "audience": "what the presenter has the whole audience do to order the gadget right now, said to "
                "them: pretend to dial, wave their phones, shout its name; harmless and singling nobody out",
            },
            omit=frozenset({"dare"}),
        ),
        repeats=1,
    ),
]

# The format's other slides, for its free slides (and to stand in for a part's slide that none of the part's generators
# can make): memes most of all (D63), gifs, deep questions and full-screen photos, which a talk may have any number of
# (so that the free slides of a long one, without fair use too, never run out of slides), the press, a fun fact, a quiz
# and a tier list
_OTHERS: Final = {
    "Meme": 2.5,
    "Full Screen Gif": 1.2,
    "Full Screen Neutral Images": 0.8,
    "Full Screen Pixabay Deep": 0.6,
    "News Headline": 0.6,
    "Fun Fact": 0.5,
    "Quiz": 0.4,
    "Tier List": 0.4,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(
        slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Infomercial)")
        for name, weight in _OTHERS.items()
    ),
    provocation(PACK, ARC, 1.4, _variables, "Infomercial", "as an infomercial shouts them"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag an infomercial may have (see presentation_schema.most_slides): each kind once, so that a part
# of two slides has two kinds, but for the statements, as many as "But wait" and the call to order may have (full-bleed
# photos aren't capped, as the TED-like talks' aren't), and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 2,
    "single_image": 1,
    "two_captions": 1,
    "three_captions": 1,
    "process": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
