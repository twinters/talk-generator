from collections.abc import Collection

from talkgenerator.schema.content_generator_structures import (
    ConceptNetMapper,
    CountryPrefixApplier,
    GoodReadsQuoteGenerator,
    JobPrefixApplier,
    SplitCaptionsGenerator,
    WikiquoteQuoteGenerator,
    create_reddit_image_generator,
    create_templated_text_generator,
    create_tracery_generator,
    generate_wikihow_bold_statement,
)
from talkgenerator.sources import (
    art_institute,
    giphy,
    inspirobot,
    openverse,
    pexels,
    pixabay,
    shitpostbot,
    unsplash,
    wikimedia_commons,
)
from talkgenerator.util.generator_util import (
    BackupGenerator,
    CombinedGenerator,
    ExternalImageListGenerator,
    InspiredTupleGenerator,
    MappedGenerator,
    NoneGenerator,
    PrefixedGenerator,
    SeededGenerator,
    TupledGenerator,
    UnseededGenerator,
)

# ===============================
# =====  CONTENT GENERATORS =====
# ===============================

# === TEXT GENERATORS ===

# TITLES
talk_title_generator = create_tracery_generator("data/text-templates/talk_title.json")
talk_ted_title_generator = create_tracery_generator("data/text-templates/talk_title.json", "ted_title")
talk_subtitle_generator = create_tracery_generator("data/text-templates/talk_subtitle.json")


def talk_title_generator_if_not_generated(presentation_context):
    if presentation_context["title"] is not None:
        return presentation_context["title"]
    return talk_title_generator(presentation_context)


default_slide_title_generator = create_templated_text_generator("data/text-templates/default_slide_title.txt")
deep_abstract_generator = create_templated_text_generator("data/text-templates/deep_abstract.txt")

default_or_no_title_generator = CombinedGenerator((1, default_slide_title_generator), (1, NoneGenerator()))

anticipation_title_generator = create_templated_text_generator("data/text-templates/anticipation_title.txt")

conclusion_title_generator = create_templated_text_generator("data/text-templates/conclusion_title.txt")
inspiration_title_generator = create_templated_text_generator("data/text-templates/inspiration.txt")
anecdote_title_generator = create_templated_text_generator("data/text-templates/anecdote_title.txt")
history_title_generator = create_templated_text_generator("data/text-templates/history.txt")
history_person_title_generator = create_templated_text_generator("data/text-templates/history_person.txt")
history_and_history_person_title_generator = CombinedGenerator(
    (4, history_title_generator), (6, history_person_title_generator)
)
about_me_title_generator = create_templated_text_generator("data/text-templates/about_me_title.txt")

# NAMES
historical_name_generator = create_tracery_generator("data/text-templates/name.json", "title_name")
full_name_generator = create_tracery_generator("data/text-templates/name.json", "full_name")

# ABOUT ME
_about_me_facts_grammar = "data/text-templates/about_me_facts.json"
book_description_generator = create_tracery_generator(_about_me_facts_grammar, "book_description")
location_description_generator = create_tracery_generator(_about_me_facts_grammar, "location_description")
hobby_description_generator = create_tracery_generator(_about_me_facts_grammar, "hobby_description")
job_generator = create_tracery_generator(_about_me_facts_grammar, "job")
country_generator = create_tracery_generator(_about_me_facts_grammar, "country")

# BOLD STATEMENTS
wikihow_bold_statement_generator = generate_wikihow_bold_statement

# PROMPTS & CHALLENGES

anecdote_prompt_generator = create_templated_text_generator("data/text-templates/anecdote_prompt.txt")

# QUOTES: mostly Goodreads, with Wikiquote for variety and as a backup when one of them fails
quote_generator = CombinedGenerator((3, GoodReadsQuoteGenerator(250)), (1, WikiquoteQuoteGenerator(250)))
short_quote_generator = CombinedGenerator((3, GoodReadsQuoteGenerator(140)), (1, WikiquoteQuoteGenerator(140)))

# DOUBLE CAPTIONS

_double_image_captions_generator = create_templated_text_generator("data/text-templates/double_captions.txt")
_triple_image_captions_generator = create_templated_text_generator("data/text-templates/triple_captions.txt")
_historic_double_captions_generator = create_templated_text_generator(
    "data/text-templates/historic_double_captions.txt"
)

double_image_captions_generator = SplitCaptionsGenerator(_double_image_captions_generator)
triple_image_captions_generator = SplitCaptionsGenerator(_triple_image_captions_generator)
historic_double_captions_generator = SplitCaptionsGenerator(_historic_double_captions_generator)

# Conclusions
_conclusions_tuple_grammar = "data/text-templates/conclusion_tuple.json"
conclusion_two_captions_tuple_generator = SplitCaptionsGenerator(
    create_tracery_generator(_conclusions_tuple_grammar, "two_conclusions")
)

conclusion_three_captions_tuple_generator = SplitCaptionsGenerator(
    create_tracery_generator(_conclusions_tuple_grammar, "three_conclusions")
)

# === IMAGE GENERATORS ===

# INSPIROBOT
inspirobot_image_generator = inspirobot.get_random_inspirobot_image

# GIFS

reddit_gif_generator = create_reddit_image_generator("gifs", "gif", "gifextra", "nonononoYES")
giphy_gif_generator = SeededGenerator(ExternalImageListGenerator(giphy.search_gifs))

combined_gif_generator = CombinedGenerator((1, reddit_gif_generator), (1, giphy_gif_generator))

# REDDIT

meme_reddit_image_generator = create_reddit_image_generator(
    "meme",
    "memes",
    "MemeEconomy",
    "wholesomememes",
    "dankmemes",
    "AdviceAnimals",
    "comics",
)
weird_reddit_image_generator = create_reddit_image_generator(
    "hmmm",
    "hmm",
    "wtf",
    "wtfstockphotos",
    "weirdstockphotos",
    "darkstockphotos",
    "photoshopbattles",
    "confusing_perspective",
    "cursedimages",
    "HybridAnimals",
    "EyeBleach",
    "natureismetal",
    "195",
)

neutral_reddit_image_generator = create_reddit_image_generator(
    "Cinemagraphs",
    "itookapicture",
    "Art",
    "artstore",
    "pics",
    "analog",
    "ExposurePorn",
    "Illustration",
)

shitpostbot_image_generator = ExternalImageListGenerator(
    SeededGenerator(BackupGenerator(shitpostbot.search_images_rated, shitpostbot.get_random_images_rated)),
    weighted=True,
)

weird_punchline_static_image_generator = CombinedGenerator(
    (4, weird_reddit_image_generator),
    (6, shitpostbot_image_generator),
    (1, meme_reddit_image_generator),
)

weird_punchline_image_generator = CombinedGenerator(
    (10, weird_reddit_image_generator),
    (8, shitpostbot_image_generator),
    (6, combined_gif_generator),
    (1, meme_reddit_image_generator),
)


# UNSPLASH
generate_unsplash_image_from_word = ExternalImageListGenerator(unsplash.search_photos, check_image_validness=False)
generate_random_unsplash_image_from_word = ExternalImageListGenerator(
    unsplash.random_as_list, check_image_validness=False
)
generate_unsplash_image = SeededGenerator(generate_unsplash_image_from_word)
generate_random_unsplash_image = SeededGenerator(generate_random_unsplash_image_from_word)

# PIXABAY
generate_pixabay_image_from_word = ExternalImageListGenerator(pixabay.search_photos)
generate_horizontal_pixabay_image_from_word = ExternalImageListGenerator(pixabay.search_horizontal)
generate_pixabay_image = SeededGenerator(generate_pixabay_image_from_word)
# PEXELS

generate_pexels_image_from_word = ExternalImageListGenerator(pexels.search_photos)
generate_pexels_image = SeededGenerator(generate_pexels_image_from_word)

# OPENVERSE (openly licensed photos from Flickr, museums, Wikimedia, ...)
generate_openverse_image_from_word = ExternalImageListGenerator(openverse.search_photos)
generate_openverse_image = SeededGenerator(generate_openverse_image_from_word)

# WIKIMEDIA COMMONS & ART INSTITUTE OF CHICAGO (old photos and public domain artworks)
generate_historic_photo_from_word = ExternalImageListGenerator(wikimedia_commons.search_historic_photos)
generate_artwork_from_word = ExternalImageListGenerator(art_institute.search_artworks)
generate_portrait_artwork_from_word = PrefixedGenerator("portrait", generate_artwork_from_word)

# COPYRIGHT FREE

copyright_free_generator = CombinedGenerator(
    (1, generate_unsplash_image),
    (1, generate_pixabay_image),
    (1, generate_pexels_image),
    (0.1, generate_openverse_image),
    (0.01, generate_random_unsplash_image),
)
copyright_free_generator_from_word = CombinedGenerator(
    (1, generate_unsplash_image_from_word),
    (1, generate_pixabay_image_from_word),
    (1, generate_pexels_image_from_word),
    (0.1, generate_openverse_image_from_word),
    (0.01, generate_random_unsplash_image_from_word),
)

generate_horizontal_pixabay_image = CombinedGenerator(
    (100, SeededGenerator(generate_horizontal_pixabay_image_from_word)),
    # Backup:
    (0.01, copyright_free_generator),
)

copyright_free_related_generator_from_word = ConceptNetMapper(copyright_free_generator_from_word)
copyright_free_related_generator = SeededGenerator(copyright_free_related_generator_from_word)


def copyright_free_prefixed_generator(prefixes: str | Collection[str]):
    return SeededGenerator(copyright_free_prefixed_generator_from_word(prefixes))


def copyright_free_prefixed_generator_from_word(prefixes: str | Collection[str]):
    if isinstance(prefixes, str):
        return PrefixedGenerator(prefixes, copyright_free_generator_from_word)
    generators = [(1, PrefixedGenerator(p, copyright_free_generator_from_word)) for p in prefixes]
    return CombinedGenerator(*generators)


weird_copyright_free_generator = copyright_free_prefixed_generator(["weird", "humor", "funny"])
normal_or_weird_copyright_free_generator = CombinedGenerator(
    (1, copyright_free_generator), (1, weird_copyright_free_generator)
)

# NEUTRAL

neutral_image_generator = CombinedGenerator(
    (1000, copyright_free_generator),
    (300, neutral_reddit_image_generator),
)

neutral_image_generator_from_word = CombinedGenerator(
    (1000, copyright_free_generator_from_word),
    (300, UnseededGenerator(neutral_reddit_image_generator)),
)

neutral_or_weird_image_generator = CombinedGenerator((1, neutral_image_generator), (1, weird_punchline_image_generator))

# OLD/VINTAGE: Reddit's vintage subreddits, with old photos and artworks as reliable alternatives
vintage_person_generator = CombinedGenerator(
    (3, create_reddit_image_generator("OldSchoolCool")),
    (1, SeededGenerator(generate_portrait_artwork_from_word)),
)
vintage_picture_generator = CombinedGenerator(
    (3, create_reddit_image_generator("TheWayWeWere", "100yearsago", "ColorizedHistory")),
    (1, SeededGenerator(generate_historic_photo_from_word)),
    (1, SeededGenerator(generate_artwork_from_word)),
)

# Copyright-free versions (ted schema)
historic_person_copyright_free_generator = CombinedGenerator(
    (2, copyright_free_prefixed_generator(["historic person", "person", "man", "woman"])),
    (1, SeededGenerator(generate_portrait_artwork_from_word)),
)
historic_copyright_free_generator = CombinedGenerator(
    (2, copyright_free_prefixed_generator(["vintage", "historic", "old", "ancient"])),
    (1, SeededGenerator(generate_historic_photo_from_word)),
    (1, SeededGenerator(generate_artwork_from_word)),
)

reddit_book_cover_generator = create_reddit_image_generator("BookCovers", "fakebookcovers", "coverdesign", "bookdesign")

reddit_location_image_generator = create_reddit_image_generator(
    "evilbuildings", "itookapicture", "SkyPorn", "EarthPorn"
)

# TUPLED ABOUT ME

about_me_hobby_tuple_generator = TupledGenerator(hobby_description_generator, weird_punchline_image_generator)
about_me_book_tuple_generator = TupledGenerator(book_description_generator, reddit_book_cover_generator)
about_me_location_tuple_generator = TupledGenerator(location_description_generator, reddit_location_image_generator)

about_me_job_tuple_generator = MappedGenerator(
    InspiredTupleGenerator(MappedGenerator(job_generator, str.title), neutral_image_generator_from_word),
    JobPrefixApplier(),
)

about_me_country_tuple_generator = MappedGenerator(
    InspiredTupleGenerator(country_generator, neutral_image_generator_from_word),
    CountryPrefixApplier(),
)

about_me_location_or_country_tuple_generator = CombinedGenerator(
    (3, about_me_country_tuple_generator), (1, about_me_location_tuple_generator)
)

# Charts

reddit_chart_generator = create_reddit_image_generator("dataisbeautiful", "funnycharts", "charts")
