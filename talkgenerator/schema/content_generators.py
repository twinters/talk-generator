from collections.abc import Collection

from talkgenerator.images.slots import ImageSlot
from talkgenerator.schema.content_generator_structures import (
    ConceptNetMapper,
    CountryPrefixApplier,
    GoodReadsQuoteGenerator,
    JobPrefixApplier,
    SplitCaptionsGenerator,
    WikiquoteQuoteGenerator,
    create_tracery_generator,
    generate_wikihow_bold_statement,
)
from talkgenerator.sources import packs, wikihow
from talkgenerator.util import language_util, random_util
from talkgenerator.util.generator_util import (
    CombinedGenerator,
    InspiredTupleGenerator,
    MappedGenerator,
    NoneGenerator,
    PrefixedGenerator,
    SeededGenerator,
    TupledGenerator,
)

# ===============================
# =====  CONTENT GENERATORS =====
# ===============================

# === TEXT GENERATORS ===
# Their templates are the TED content pack's (data/packs/ted: see talkgenerator.sources.packs)
_PACK = packs.pack(packs.TED)

# TITLES
talk_title_generator = _PACK.tracery("title.talk_title")
talk_ted_title_generator = _PACK.tracery("title.ted_title")
talk_subtitle_generator = _PACK.tracery("title.subtitle")


def talk_title_generator_if_not_generated(presentation_context):
    if presentation_context["title"] is not None:
        return presentation_context["title"]
    return talk_title_generator(presentation_context)


def wikihow_title_generator(presentation_context) -> str | None:
    """A wikiHow "How to ..." title about the seed (one of wikiHow's how-tos that its search finds), which the
    language model that writes a talk may pick for it (see talkgenerator.titles)."""
    action = random_util.choice_optional(wikihow.get_related_wikihow_actions(presentation_context["seed"]))
    return f"How to {action}" if action else None


default_slide_title_generator = _PACK.templates("images.slide_title")
deep_abstract_generator = _PACK.templates("statements.deep_question")

default_or_no_title_generator = CombinedGenerator((1, default_slide_title_generator), (1, NoneGenerator()))

anticipation_title_generator = _PACK.templates("images.anticipation_title")

conclusion_title_generator = _PACK.templates("conclusions.conclusion_title")
# (a confident conclusion over a real chart from the internet, which it supposedly proves: PowerPoint karaoke's)
chart_conclusion_generator = _PACK.templates("charts.chart_conclusion")


def chart_conclusion_or_none_generator(presentation_context):
    """A real chart's confident conclusion two times in three, and else none, for a bare chart. (Not a
    CombinedGenerator with a NoneGenerator, which tries its other generators when one gives None.)"""
    if random_util.random() < 2 / 3:
        return chart_conclusion_generator(presentation_context)
    return None


inspiration_title_generator = _PACK.templates("images.inspiration_title")
history_title_generator = _PACK.templates("history.history_title")
history_person_title_generator = _PACK.templates("history.history_person_title")
history_and_history_person_title_generator = CombinedGenerator(
    (4, history_title_generator), (6, history_person_title_generator)
)
about_me_title_generator = _PACK.templates("about_me.about_me_title")

# NAMES
historical_name_generator = create_tracery_generator("data/text-templates/name.json", "title_name")
full_name_generator = create_tracery_generator("data/text-templates/name.json", "full_name")

# ABOUT ME
book_description_generator = _PACK.tracery("about_me.book_description")
location_description_generator = _PACK.tracery("about_me.location_description")
hobby_description_generator = _PACK.tracery("about_me.hobby_description")
job_generator = _PACK.tracery("about_me.job")
country_generator = _PACK.tracery("about_me.country")

# BOLD STATEMENTS
wikihow_bold_statement_generator = generate_wikihow_bold_statement

# PROMPTS & CHALLENGES

anecdote_prompt_generator = _PACK.templates("statements.anecdote")

# QUOTES: mostly Goodreads, with Wikiquote for variety and as a backup when one of them fails
quote_generator = CombinedGenerator((3, GoodReadsQuoteGenerator(250)), (1, WikiquoteQuoteGenerator(250)))
short_quote_generator = CombinedGenerator((3, GoodReadsQuoteGenerator(140)), (1, WikiquoteQuoteGenerator(140)))

# DOUBLE CAPTIONS

_double_image_captions_generator = _PACK.templates("captions.two_captions")
_triple_image_captions_generator = _PACK.templates("captions.three_captions")
_historic_double_captions_generator = _PACK.templates("history.historic_captions")

double_image_captions_generator = SplitCaptionsGenerator(_double_image_captions_generator)
triple_image_captions_generator = SplitCaptionsGenerator(_triple_image_captions_generator)
historic_double_captions_generator = SplitCaptionsGenerator(_historic_double_captions_generator)

# Conclusions
conclusion_two_captions_tuple_generator = SplitCaptionsGenerator(_PACK.tracery("conclusions.two_conclusions"))
conclusion_three_captions_tuple_generator = SplitCaptionsGenerator(_PACK.tracery("conclusions.three_conclusions"))

# === IMAGE GENERATORS ===
# Image slots (see talkgenerator.images.slots): what kind of image a slide asks for, in which look. Called with a
# presentation context, a slot finds an image for its seed, the slide's topic, as v4's image generators did; and
# their weighted mixes of sources became the looks' source weights (see talkgenerator.images.profiles).

# INSPIROBOT
inspirobot_image_generator = ImageSlot("an inspirational poster, made by InspiroBot", aesthetic="inspirobot")

# GIFS
reddit_gif_generator = ImageSlot("a gif from Reddit", aesthetic="gifs", sources=("reddit:gifs",))
giphy_gif_generator = ImageSlot("a gif from GIPHY", aesthetic="gifs", sources=("giphy",))
combined_gif_generator = ImageSlot("a gif", aesthetic="gifs")

# MEMES WITH LIVE CAPTIONS: Imgflip's templates, whose captions talkgenerator writes on them (talkgenerator.sources.memes)
meme_template_generator = ImageSlot("a meme template, captioned live", aesthetic="meme-templates", sources=("imgflip",))

# REDDIT, AND SHITPOSTBOT
meme_reddit_image_generator = ImageSlot("a meme", aesthetic="memes")
weird_reddit_image_generator = ImageSlot("a weird picture from Reddit", aesthetic="weird", sources=("reddit:weird",))
neutral_reddit_image_generator = ImageSlot("a photo or artwork from Reddit", aesthetic="pictures")
shitpostbot_image_generator = ImageSlot("one of ShitpostBot's images", aesthetic="weird", sources=("shitpostbot",))

weird_punchline_static_image_generator = ImageSlot(
    "a weird picture or meme, as a punchline", aesthetic="meme-chaos-still"
)
weird_punchline_image_generator = ImageSlot("a weird picture, gif or meme, as a punchline", aesthetic="meme-chaos")

# STOCK PHOTOS
generate_unsplash_image = ImageSlot("a photo from Unsplash", sources=("unsplash", "unsplash-random"))
generate_unsplash_image_from_word = generate_unsplash_image.from_word
generate_random_unsplash_image = ImageSlot("a random photo from Unsplash", sources=("unsplash-random",))
generate_random_unsplash_image_from_word = generate_random_unsplash_image.from_word
generate_pixabay_image = ImageSlot("a photo from Pixabay", sources=("pixabay",))
generate_pixabay_image_from_word = generate_pixabay_image.from_word
generate_pexels_image = ImageSlot("a photo from Pexels", sources=("pexels",))
generate_pexels_image_from_word = generate_pexels_image.from_word
generate_openverse_image = ImageSlot("an openly licensed photo", sources=("openverse",))
generate_openverse_image_from_word = generate_openverse_image.from_word

# OLD PHOTOS AND ARTWORKS (public domain and openly licensed)
generate_historic_photo_from_word = ImageSlot(
    "an old photograph", aesthetic="vintage", sources=("wikimedia",)
).from_word
generate_artwork_from_word = ImageSlot("an artwork", aesthetic="museum", sources=("art-institute",)).from_word
generate_portrait_artwork_from_word = PrefixedGenerator("portrait", generate_artwork_from_word)

# COPYRIGHT FREE (no fair use: the stock sites, and openly licensed photos now and then)
copyright_free_generator = ImageSlot("a photo of the slide's topic", aesthetic="photo")
copyright_free_generator_from_word = copyright_free_generator.from_word

# Behind a slide's big text: a calm landscape photo (v4 took Pixabay's horizontal photos)
generate_horizontal_pixabay_image = ImageSlot("a calm photo behind the slide's text", aesthetic="calm-backdrop")
generate_horizontal_pixabay_image_from_word = generate_horizontal_pixabay_image.from_word

copyright_free_related_generator_from_word = ConceptNetMapper(copyright_free_generator_from_word)
copyright_free_related_generator = SeededGenerator(copyright_free_related_generator_from_word)


def copyright_free_prefixed_generator(prefixes: str | Collection[str]):
    return SeededGenerator(copyright_free_prefixed_generator_from_word(prefixes))


def copyright_free_prefixed_generator_from_word(prefixes: str | Collection[str]):
    if isinstance(prefixes, str):
        return PrefixedGenerator(prefixes, copyright_free_generator_from_word)
    generators = [(1, PrefixedGenerator(p, copyright_free_generator_from_word)) for p in prefixes]
    return CombinedGenerator(*generators)


weird_copyright_free_generator = ImageSlot("a weird or funny stock photo", aesthetic="weird-stock")
normal_or_weird_copyright_free_generator = CombinedGenerator(
    (1, copyright_free_generator), (1, weird_copyright_free_generator)
)

# NEUTRAL: stock photos, and now and then Reddit's photos and art
neutral_image_generator = ImageSlot("a photo of the slide's topic", aesthetic="neutral")
neutral_image_generator_from_word = neutral_image_generator.from_word

neutral_or_weird_image_generator = CombinedGenerator((1, neutral_image_generator), (1, weird_punchline_image_generator))

# WITH BACKUPS: Reddit and GIPHY need keys, and Reddit can be blocked or rate limited. These use them when they can,
# and otherwise looks with sources that need no key (or stock photos of weird things), so that slides needing them
# stay possible.
weird_image_with_backup_generator = ImageSlot("a weird picture", aesthetic="weird")
gif_with_backup_generator = ImageSlot("a gif, or else a weird picture", aesthetic="gifs", backups=("weird",))

# OLD/VINTAGE: old photos in black and white or sepia, and old photos of people and painted portraits
vintage_person_generator = ImageSlot("an old photo or a painted portrait of someone", aesthetic="old-people")
vintage_picture_generator = ImageSlot("an old photograph", aesthetic="vintage")

# Copyright-free versions (ted schema)
historic_person_copyright_free_generator = ImageSlot("a portrait of someone", aesthetic="portrait")
historic_copyright_free_generator = ImageSlot("an old photograph", aesthetic="vintage")

reddit_book_cover_generator = ImageSlot("a book cover", aesthetic="book-covers")

reddit_location_image_generator = ImageSlot("a place", aesthetic="places")

# Where the presenter comes from: now and then its flag (for a country), else photos of it
country_image_generator = ImageSlot("where the presenter comes from: its flag, or a photo of it", aesthetic="country")
country_image_generator_from_word = country_image_generator.from_word

# GENERATED, IN A TALK THAT GENERATES PICTURES (see talkgenerator.images.generation): what stock photos can't show well
# prefers a generated picture. Each slot's look is the one its slides had, whose stock photo stands in for the
# generated picture until it's in (or for good, in a talk that generates none).
hobby_image_generator = ImageSlot("the presenter's weird hobby", aesthetic="meme-chaos", generate=True)
book_cover_generator = ImageSlot("the cover of the book the presenter wrote", aesthetic="book-covers", generate=True)
historic_moment_generator = ImageSlot(
    "an old photograph of a moment in the concept's made-up history", aesthetic="vintage", generate=True
)
historic_figure_generator = ImageSlot(
    "a portrait of the made-up historical figure", aesthetic="old-people", generate=True
)
historic_figure_copyright_free_generator = ImageSlot(
    "a portrait of the made-up historical figure", aesthetic="portrait", generate=True
)
news_photo_generator = ImageSlot("the photo of the made-up news story", aesthetic="neutral", generate=True)
news_photo_copyright_free_generator = ImageSlot("the photo of the made-up news story", aesthetic="photo", generate=True)

# TUPLED ABOUT ME

about_me_hobby_tuple_generator = TupledGenerator(hobby_description_generator, weird_punchline_image_generator)
about_me_book_tuple_generator = TupledGenerator(book_description_generator, reddit_book_cover_generator)
about_me_location_tuple_generator = TupledGenerator(location_description_generator, reddit_location_image_generator)

about_me_job_tuple_generator = MappedGenerator(
    InspiredTupleGenerator(MappedGenerator(job_generator, language_util.title_case), neutral_image_generator_from_word),
    JobPrefixApplier(),
)

about_me_country_tuple_generator = MappedGenerator(
    InspiredTupleGenerator(country_generator, country_image_generator_from_word),
    CountryPrefixApplier(),
)

about_me_location_or_country_tuple_generator = CombinedGenerator(
    (3, about_me_country_tuple_generator), (1, about_me_location_tuple_generator)
)

# Charts

reddit_chart_generator = ImageSlot("a chart, badly made or funny", aesthetic="bad-charts")
