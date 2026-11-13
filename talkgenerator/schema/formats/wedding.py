"""The wedding toast (docs/v5-plan.md, section 7; D79): the best man or the maid of honour raises a glass to their best
friend, who is marrying the talk's topic, however absurd.

Its arc goes from who the speaker is (an old photo of the two friends, the best friend then and now, or "For those
who don't know me...") through how the couple met (a photo of the topic, the day they met; their love story as a
timeline; or the best friend's happiness since, as a line chart whose second line, their free time, falls away on a
click), an embarrassing story (the incident, full-bleed; the red flags everyone ignored; or a post from the night they
met), why they're perfect together (a Venn diagram of what they share, the two side by side, or the best friend's great
loves ranked, the topic winning by far) and some marriage advice (three photos of it, a statement over a backdrop, or
the pyramid of a happy marriage) to the toast (the whole room raising their glasses, as audience participation; the
toast over a backdrop; or "To the happy couple!" over a photo), before its closer says it once more (D76), outside its
slides. A short toast keeps who the speaker is, how the couple met, the story and the toast; a quarter of a talk's
slides are free (D63), for gifs, memes, full-screen pictures, deep questions over photos, a quote and its own
provocations ("Forever.", over a full-screen picture), and a long one gives how they met, the story, the couple and the
advice a second slide each. The best friend's first name comes from the topic (see talkgenerator.schema.formats.friend),
one that goes with anyone ("they", never "he" or "she"), so that a classic toast's slides name the same best friend as
its title. The toasts are drink-free: glasses go up, and nothing in them is named.

The best man or maid of honour gives a wedding toast far more often than the other personas, and a life coach, a
retiree and a motivational speaker a little more often; its themes are vintage paper and clean keynotes more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import Recipe, Variant
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    Format,
    KindSlideGenerator,
    Made,
    different,
    friend,
    maybe,
    photos,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.util import language_util, random_util

PACK: Final = "wedding"

ARC: Final = Arc(
    (
        Part("intro", rank=3),
        Part("how_they_met", 1, 2, rank=1),
        Part("story", 1, 2, rank=2),
        Part("couple", 1, 2, rank=4),
        Part("advice", 1, 2, rank=5),
        Part("toast", rank=0),
    ),
    free=0.25,  # (D63: two slides of ten for gifs, memes and pictures, as in the other formats)
)

WEDDING: Final = Format(
    brief="a wedding toast by the best man or the maid of honour, for their best friend, who is marrying the topic, "
    "however absurd: who the speaker is, how the couple met, an embarrassing story, why they're perfect together, "
    "some marriage advice and the toast itself, with the whole room raising their glasses. The best friend has a "
    "first name of your choosing that suits anyone (never the word 'they' as a name), and the toast speaks of them "
    "as 'they'; the topic is the one they marry, played straight as a beloved "
    "partner, and the speech is warm, rambling and a little too honest; glasses are raised, but no drink is named",
    title_hint="like a wedding toast's title: the best friend and the topic as a couple, or a fond and embarrassing "
    "promise, in a few words",
    job_hint="who they are to the couple, as a toast introduces them: best man, maid of honour, or a best friend since "
    "nursery school",
    personas={"best_man": 9, "life_coach": 1.5, "retiree": 1.5, "motivational_speaker": 1.3},
    themes={
        "glossy magazine": 2.5,
        "vintage paper": 3,
        "clean keynote": 2,
        "1997 WordArt": 1.5,
        "neon": 1.2,
        "hacker terminal": 0.3,
        "blueprint": 0.4,
        "corporate": 0.5,
        "brutalist": 0.5,
        "clip-art corporate": 0.6,
    },
    arc=ARC,
    # (its closer is the toast's last words, to the happy couple: D76)
    closer=Closer(said("happy_couple"), presenter),
    scene="wedding",
)


def _topic(context: dict[str, Any]) -> str:
    return str(context.get("topic") or context["seed"])


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic (the one the best friend marries), the
    presenter, the title and the best friend's first name."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["friend"] = friend(_topic(context))
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


_LONGEST_PARTNER: Final = 28  # (characters of the topic's name in a Venn diagram's circle, or on a ranking's bar)


def _partner(topic: str) -> str:
    """The one the best friend marries, as a Venn diagram's circle or a ranking's bar names it: the topic as English
    speaks of it in general ("Penguins", "Coffee", "The moon"), without its first words where that's too long."""
    words_of = language_util.generic(topic.strip()).split() or ["Love"]
    while len(" ".join(words_of)) > _LONGEST_PARTNER and len(words_of) > 1:
        words_of = words_of[1:]
    return language_util.capitalised(" ".join(words_of))[:_LONGEST_PARTNER]


# THE TITLE SLIDE: the couple, and who toasts them


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic toast's title, about the seed (the talk's topic, the one the best friend marries)."""
    return text(PACK, "title.talk_title", {**context, "friend": friend(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: old photos of the two friends (or of whatever the slide is about, which the speaker explains), a portrait for
# the best friend, photos of the topic, an odd one of the embarrassing story, and calm backdrops behind the big words.
# The day they met is the topic's own photo; the others search it otherwise (as a couple, together, in a selfie, close
# up), so that a talk's slides about the topic don't all find that one photo, and lose their slide for repeating it
_OLD = ImageSlot(
    "an old photo of the speaker and the best friend, long ago", aesthetic="vintage", backups=("old-photo", "photo")
)
_FRIEND = ImageSlot("a photo of the best friend", aesthetic="portrait", backups=("photo",))
_PARTNER = ImageSlot("a photo of the one the best friend marries", aesthetic="photo")
_CLOSE_UP = ImageSlot(
    "a photo of the one the best friend marries, close up", queries=("{} close-up", "{}"), aesthetic="photo"
)
_COUPLE = ImageSlot(
    "a photo of the happy couple: the topic, as a pair", queries=("{} couple", "{} love", "{}"), aesthetic="photo"
)
_INCIDENT = ImageSlot("an odd photo of the embarrassing story", aesthetic="weird-stock", generate=True)
_ADVICE = ImageSlot("a photo of a piece of marriage advice", queries=("{} together", "{}"), aesthetic="photo")
_SELFIE = ImageSlot("the photo the post had: a selfie with the topic", queries=("{} selfie", "{}"), aesthetic="photo")
_BACKDROP = cg.statement_backdrop_generator


# WHO THE SPEAKER IS: an old photo of the two, the best friend then and now, or a statement


def _old_photo(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "intro.old_photo_title", _variables(context))
    return ({"title": title}, {"image": _OLD(context)}) if title else None


def _then_and_now(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    captions = (text(PACK, "intro.then_now", variables) or "").split("|")
    if len(captions) != 2:
        return None
    then = _OLD(context)
    texts = {
        "title": maybe(0.7, text(PACK, "intro.then_now_title", variables)),
        "caption_1": captions[0].strip(),
        "caption_2": captions[1].strip(),
    }
    return texts, {"image_1": then, "image_2": photos(_FRIEND, context, 1, avoid=[then])[0]}


def _who_am_i(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "intro.who_am_i", _variables(context))
    return ({"text": said}, {"background": _BACKDROP(context)}) if said else None


# HOW THEY MET: the day they met, their love story as a timeline, or the best friend's happiness since


def _day_they_met(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "met.day_title", _variables(context))
    # (a photo of the topic itself, the one the best friend met, whatever the slide's own seed wandered to)
    return ({"title": title}, {"image": _PARTNER.find(_topic(context))}) if title else None


def _love_story(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "met.first_event", variables), text(PACK, "met.last_event", variables)
    middle = different(PACK, "met.event", variables, count - 2)
    title = text(PACK, "met.story_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    known = words(PACK, "met.moment")  # (the earliest first)
    dates = [known[index] for index in sorted(random_util.sample(range(len(known)), count - 1))]
    dates.append(random_util.choice(words(PACK, "met.today")))
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(dates, [first, *middle, last], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


def _happiness(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "met.chart_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "met.chart_x", variables),
        "y_axis": text(PACK, "met.chart_y", variables),
        "shape": random_util.choice(("rising", "exponential", "hockey stick", "plateau")),
        "line": text(PACK, "met.chart_line", variables),
        "second_line": maybe(0.8, text(PACK, "met.chart_second", variables)),
        "second_shape": random_util.choice(("falling", "crash", "dip")),
        "event": maybe(0.7, text(PACK, "met.chart_event", variables)),
    }, {}


# THE STORY: the incident, full-bleed, the red flags everyone ignored, or a post from that night


def _incident(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "story.incident_title", _variables(context))
    return ({"title": title}, {"image": _INCIDENT(context)}) if title else None


def _red_flags(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.choice((3, 4, 4, 5))
    flags = different(PACK, "story.flag", variables, count - 1)
    title, punchline = text(PACK, "story.flags_title", variables), text(PACK, "story.flag_punchline", variables)
    if not title or not punchline or len(flags) < count - 1:
        return None
    return {"title": title, **_items("flag", [*flags, punchline])}, {}


def _handle(name: str, topic: str, smitten: bool) -> str:
    """A made-up username for the post's author: the best friend's smitten, the speaker's a best friend's."""
    first = "".join(letter for letter in name.split()[0].lower() if letter.isalpha()) if name.split() else "bestie"
    loved = "".join(letter for letter in topic.lower() if letter.isalnum())[:10] or "love"
    number = random_util.randint(2, 99)
    if smitten:
        return random_util.choice((f"{first}_in_love", f"{first}_and_{loved}", f"{first}{number}"))[:24]
    return random_util.choice((f"{first}_the_bestie", f"real_{first}", f"{first}{number}"))[:24]


def _that_night(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    by_friend = random_util.random() < 0.6 or not context.get("presenter")
    post = text(PACK, "story.friend_post" if by_friend else "story.speaker_post", variables)
    if not post:
        return None
    author = variables["friend"] if by_friend else str(context["presenter"])
    texts = {
        "title": maybe(0.8, text(PACK, "story.post_title", variables)),
        "author": author[:30],
        "handle": _handle(author, _topic(context), by_friend),
        "text": post,
    }
    return texts, {"photo": _SELFIE(context)}


# THE COUPLE: what they share, the two side by side, or the best friend's great loves, ranked


def _perfect_match(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title, overlap = text(PACK, "couple.venn_title", variables), text(PACK, "couple.overlap", variables)
    third = text(PACK, "couple.third_circle", variables) if random_util.random() < 0.4 else None
    if not title or not overlap:
        return None
    circles = [variables["friend"], _partner(_topic(context)), *([third] if third else [])]
    return {"title": title, **_items("circle", circles), "overlap": overlap}, {}


def _side_by_side(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    captions = (text(PACK, "couple.pair", variables) or "").split("|")
    if len(captions) != 2:
        return None
    texts = {
        "title": maybe(0.8, text(PACK, "couple.side_title", variables)),
        "caption_1": captions[0].strip(),
        "caption_2": captions[1].strip(),
    }
    portrait = _FRIEND(context)
    return texts, {"image_1": portrait, "image_2": photos(_CLOSE_UP, context, 1, avoid=[portrait])[0]}


def _great_loves(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    loves = different(PACK, "couple.old_love", variables, random_util.randint(2, 3))
    title = text(PACK, "couple.loves_title", variables)
    if not title or len(loves) < 2:
        return None
    return {
        "title": title,
        "bars": " | ".join([*loves, _partner(_topic(context))]),
        "value_axis": maybe(0.8, text(PACK, "couple.loves_axis", variables)),
    }, {}


# THE ADVICE: three photos of it, a statement over a backdrop, or the pyramid of a happy marriage


def _advice(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    tips = different(PACK, "advice.tip", variables, 2)
    punchline = text(PACK, "advice.tip_punchline", variables)
    if len(tips) < 2 or not punchline:
        return None
    texts = {"title": text(PACK, "advice.advice_title", variables), **_items("caption", [*tips, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_ADVICE, context, 3), 1)}


def _marriage_is(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "advice.marriage_is", _variables(context))
    return ({"text": said}, {"background": _BACKDROP(context)}) if said else None


def _pyramid(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    levels = different(PACK, "advice.pyramid_level", variables, random_util.randint(2, 3))
    title, top = text(PACK, "advice.pyramid_title", variables), text(PACK, "advice.pyramid_top", variables)
    if not title or not top or len(levels) < 2:
        return None
    return {"title": title, **_items("level", [top, *levels])}, {}


# THE TOAST: the whole room raises their glasses, the toast over a backdrop, or "To the happy couple!"


def _raise_your_glasses(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "toast.audience", _variables(context))
    return ({"audience": said}, {}) if said else None


def _toast(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "toast.toast", _variables(context))
    return ({"text": said}, {"background": _BACKDROP(context)}) if said else None


def _happy_couple(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "toast.couple_title", _variables(context))
    return ({"title": title}, {"image": _COUPLE(context)}) if title else None


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
        name=f"{name} (Wedding)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a wedding toast's slide has it: a few words"
_FRIEND_HINT = "the best friend, by the first name the talk gave them (they're 'they')"
_PARTNER_HINT = "the one the best friend marries: the topic, by its name"
_FEW_WORDS = "in a few words"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Wedding)",
        llm=Recipe("title"),
    ),
    # Who the speaker is
    _part(
        "intro",
        1.4,
        "image",
        _old_photo,
        ["single_image"],
        "Old Photo",
        Recipe(
            "image",
            (_OLD,),
            brief="Who the speaker is: an old photo, under a title that says it's the speaker and the best friend, "
            "long ago (the speaker will explain whatever the photo shows)",
            hints={"title": "a title naming the speaker and the best friend, and the year or the occasion"},
        ),
    ),
    _part(
        "intro",
        1.1,
        "two_columns",
        _then_and_now,
        ["two_captions"],
        "Then and Now",
        Recipe(
            "two_columns",
            (_OLD, _FRIEND),
            brief="The best friend then and now, as two captioned photos: an old one, and one of them since",
            hints={
                "title": _TITLE_HINT + ", or empty for none",
                "caption_1": f"the best friend long ago, {_FEW_WORDS}",
                "caption_2": f"the best friend now, {_FEW_WORDS}: what the topic made of them",
            },
        ),
    ),
    _part(
        "intro",
        0.8,
        "statement",
        _who_am_i,
        ["statement"],
        "Who Am I",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="Who the speaker is, over a photo: how they know the best friend, and a hint of what's coming",
            hints={"text": "the opening lines of the toast: one or two short sentences"},
        ),
    ),
    # How they met
    _part(
        "how_they_met",
        1.4,
        "image",
        _day_they_met,
        ["single_image"],
        "The Day They Met",
        Recipe(
            "image",
            (_PARTNER,),
            brief="How the couple met: a photo of the topic, the day the best friend first saw it",
            hints={"title": "a title about the moment the best friend met the topic, naming both"},
        ),
    ),
    _part(
        "how_they_met",
        1,
        "timeline",
        _love_story,
        ["timeline", "diagram"],
        "Love Story",
        Recipe(
            "timeline",
            brief="The couple's love story as a timeline, from the first glance to today, the last moment the "
            "punchline",
            hints={
                "title": _TITLE_HINT,
                **{
                    f"date_{index}": "when it happened, counted from the day they met (the last one today)"
                    for index in range(1, 6)
                },
                **{f"event_{index}": f"what happened then, {_FEW_WORDS}" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"date_4", "event_4", "date_5", "event_5"}), "with three moments"),
                Variant(1, frozenset({"date_5", "event_5"}), "with four moments"),
                Variant(1, note="with five moments"),
            ),
        ),
    ),
    _part(
        "how_they_met",
        1,
        "chart_trend",
        _happiness,
        ["trend_chart", "chart"],
        "Happiness Since",
        Recipe(
            "chart_trend",
            brief="The best friend's happiness since meeting the topic, as a line that climbs, and as a second line "
            "that appears on a click, the punchline, something of the speaker's that fell away since (their game "
            "nights together, say)",
            hints={
                "title": "the chart's claim, about the best friend since they met the topic",
                "shape": "how the best friend's happiness goes: rising, exponential, hockey stick or plateau",
                "line": "the best friend's happiness, in the legend",
                "second_line": "what fell away since, in the legend: the punchline",
                "second_shape": "how that goes: falling, crash or dip",
                "event": "the moment they met, where the line takes off",
            },
        ),
    ),
    # The story
    _part(
        "story",
        1.4,
        "full_image",
        _incident,
        ["full_image"],
        "The Incident",
        Recipe(
            "full_image",
            (_INCIDENT,),
            brief="An embarrassing story about the best friend: an odd photo, filling the slide, that the speaker has "
            "to tell the story of, under its name",
            hints={"title": "the story's name, as friends call it, such as the incident of a year or a place"},
        ),
    ),
    _part(
        "story",
        1,
        "red_flags",
        _red_flags,
        ["red_flags"],
        "Red Flags We Ignored",
        Recipe(
            "red_flags",
            brief="The red flags everyone ignored, in hindsight: the signs that the best friend was falling for the "
            "topic, each more telling than the last, the last one the punchline",
            hints={"title": "a title that says these are the red flags everyone ignored"},
        ),
    ),
    _part(
        "story",
        0.9,
        "social_post",
        _that_night,
        ["social_post"],
        "That Night",
        Recipe(
            "social_post",
            (_SELFIE,),
            brief="A post from the night the couple met: the best friend's, smitten, or the speaker's, about losing "
            "their best friend to the topic",
            hints={
                "title": "a title such as whose post it was and when, or empty for none",
                "author": "the best friend's first name, or the speaker's name",
            },
        ),
        repeats=1,
    ),
    # The couple
    _part(
        "couple",
        1.1,
        "venn",
        _perfect_match,
        ["venn_diagram", "diagram"],
        "Perfect Match",
        Recipe(
            "venn",
            brief="Why the couple is perfect together, as a Venn diagram: the best friend in one circle, the topic in "
            "another, maybe a third, and what they all share, the punchline",
            hints={
                "title": _TITLE_HINT,
                "circle_1": _FRIEND_HINT,
                "circle_2": _PARTNER_HINT,
                "overlap": "the odd thing they share",
            },
        ),
    ),
    _part(
        "couple",
        1.2,
        "two_columns",
        _side_by_side,
        ["two_captions"],
        "Side by Side",
        Recipe(
            "two_columns",
            (_FRIEND, _CLOSE_UP),
            brief="The couple side by side, as two captioned photos: the best friend and the topic, each with a trait "
            "of theirs, the second one the reason they fit",
            hints={
                "title": _TITLE_HINT + ", or empty for none",
                "caption_1": f"the best friend's name and a trait of theirs, {_FEW_WORDS}",
                "caption_2": f"the topic's name and the trait that fits it, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "couple",
        1,
        "chart_bars",
        _great_loves,
        ["bar_chart", "chart"],
        "Great Loves",
        Recipe(
            "chart_bars",
            brief="The best friend's great loves, ranked in bars: the things they loved before (a snack, a nap, an old "
            "bike), and the topic, the last bar, the punchline, which wins by far",
            hints={
                "title": "what the ranking compares, about the best friend's loves",
                "bars": "two or three of the best friend's earlier loves (only their names), separated by |, and the "
                "topic last",
                "value_axis": "what the bars measure, such as their devotion",
            },
        ),
    ),
    # The advice
    _part(
        "advice",
        1.4,
        "three_columns",
        _advice,
        ["three_captions"],
        "Marriage Advice",
        Recipe(
            "three_columns",
            (_ADVICE, _ADVICE, _ADVICE),
            brief="Marriage advice for the couple, as three captioned photos, the last piece the punchline",
            hints={
                "title": _TITLE_HINT,
                "caption_1": f"a piece of marriage advice, {_FEW_WORDS}",
                "caption_2": f"another piece of advice, {_FEW_WORDS}",
                "caption_3": f"the last piece, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "advice",
        0.9,
        "statement",
        _marriage_is,
        ["statement"],
        "Marriage Is Like",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The speaker's wisdom on marriage, over a photo: what marriage is like, with the topic in it",
            hints={"text": "one or two short sentences of wedding wisdom that go somewhere odd"},
        ),
    ),
    _part(
        "advice",
        0.9,
        "pyramid",
        _pyramid,
        ["pyramid", "diagram"],
        "Happy Marriage Pyramid",
        Recipe(
            "pyramid",
            brief="What a happy marriage is built on, as a pyramid: the basics at its base, and at its top the "
            "punchline",
            hints={"title": _TITLE_HINT},
        ),
    ),
    # The toast
    _part(
        "toast",
        1.3,
        "dare",
        _raise_your_glasses,
        ["dare"],
        "Raise Your Glasses",
        Recipe(
            "dare",
            brief="The toast, as audience participation: the speaker has the whole room raise their glasses to the "
            "couple, the best friend and the topic, and say something together",
            hints={
                "audience": "what everyone in the room does and says, said to them, for the toast to the best friend "
                "and the topic; no drink named"
            },
            omit=frozenset({"dare"}),
            facts=False,
        ),
        repeats=1,
    ),
    _part(
        "toast",
        0.9,
        "statement",
        _toast,
        ["statement"],
        "The Toast",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The toast itself, over a photo: to the best friend and the topic",
            hints={"text": "the toast, naming the best friend and the topic, in one short sentence"},
        ),
    ),
    _part(
        "toast",
        1.1,
        "full_image",
        _happy_couple,
        ["full_image"],
        "To the Happy Couple",
        Recipe(
            "full_image",
            (_COUPLE,),
            brief="The toast: a photo of the topic, filling the slide, under the toast to the happy couple",
            hints={"title": "the toast to the happy couple, in a few words"},
        ),
    ),
]

# The format's other slides, for the free slides (and to stand in for a part's slide that none of the part's
# generators can make): memes, gifs, deep questions and full-screen photos (which a talk may have any number of, so
# that the free slides of a long one, without fair use too, never run out of slides), a quote, reviews, a fun fact
_OTHERS: Final = {
    "Meme": 1.6,  # (D63: memes more often, as in the other formats)
    "Full Screen Gif": 1.2,
    "Full Screen Pixabay Deep": 0.9,
    "Full Screen Neutral Images": 0.8,
    "Two Captions Gifs": 0.6,
    "Quote": 0.5,
    "Reviews": 0.4,
    "Fun Fact": 0.3,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Wedding)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 1.2, _variables, "Wedding", "as a wedding toast's speaker would say it to the room"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a wedding toast may have (see presentation_schema.most_slides): the TED-like talks' caps
# (each kind once, statements and pairs of photos a fifth of the slides, diagrams a fifth, charts three in ten), and a
# provocation a slide in ten at most
CAPS: Final = {**default_max_allowed_tags, "provocation": 0.1}
