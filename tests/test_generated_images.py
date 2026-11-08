"""Offline tests of generated pictures (docs/v5-plan.md, section 10.5): the image generators' adapters (against fake
servers), the rules prompts keep to, the cache, and talks that generate pictures, with a fake language model, fake
image sources and a fake image generator. Nothing goes over the network, and nothing costs anything.
"""

import base64
import hashlib
import io
import json
import os
import random
import threading

import pytest
from PIL import Image, ImageDraw

from talkgenerator import generator, settings
from talkgenerator.checks.deck import check_licenses
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.images import catalog, generation, profiles, safety
from talkgenerator.images.generation import ImageBudget
from talkgenerator.images.generators import (
    GeneratedImage,
    GenerationError,
    GenerationRateLimited,
    GenerationRefused,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
    cache,
    generator_from_spec,
    prices,
)
from talkgenerator.images.generators.flux import FluxImageGenerator
from talkgenerator.images.generators.gemini import GeminiImageGenerator
from talkgenerator.images.generators.local import Automatic1111Generator, ComfyUIGenerator
from talkgenerator.images.generators.openai_images import OpenAIImageGenerator
from talkgenerator.images.generators.openrouter import OpenRouterImageGenerator
from talkgenerator.images.generators.openrouter import forget as forget_openrouter
from talkgenerator.images.profiles import Profile, SourceUse
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import Deck
from talkgenerator.models.events import SlideReady, SlideUpdated, TalkFinished
from talkgenerator.plan.kinds import Recipe
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util import image_util
from talkgenerator.util.generator_util import StaticGenerator
from tests.test_llm_talks import FakeModel

KEY = "sk-test-0123456789abcdefghijklmnop"  # (a fake key, shaped like a real one: errors must never show it)


def _png(seed: str, size=(160, 120)) -> bytes:
    """A picture of coloured blocks, its own for every seed."""
    rng = random.Random(seed)
    picture = Image.new("RGB", size)
    draw = ImageDraw.Draw(picture)
    for row in range(3):
        for column in range(4):
            colour = tuple(rng.randrange(256) for _ in range(3))
            box = (column * size[0] // 4, row * size[1] // 3, (column + 1) * size[0] // 4, (row + 1) * size[1] // 3)
            draw.rectangle(box, fill=colour)
    output = io.BytesIO()
    picture.save(output, "PNG")
    return output.getvalue()


# FAKE SERVERS, FOR THE ADAPTERS


class FakeResponse:
    def __init__(self, status=200, data=None, content=b"", headers=None):
        self.status_code = status
        self._data = data
        self.content = content if content else json.dumps(data).encode() if data is not None else b""
        self.headers = headers or {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._data is None:
            raise ValueError("no JSON")
        return self._data


class FakeClient:
    """Answers requests with what answer(method, url, body) says, and remembers them."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def post(self, url, *, json, headers, timeout):
        self.requests.append(("POST", url, json, headers))
        return self.answer("POST", url, json)

    def get(self, url, *, headers, timeout):
        self.requests.append(("GET", url, None, headers))
        return self.answer("GET", url, None)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


REQUEST = ImageRequest(
    prompt="a cat wearing sunglasses", aspect_ratio="3:2", style="a photograph", avoid="logos", seed=7
)


def test_openai_gets_the_prompt_size_and_quality_and_answers_with_the_picture():
    picture = _png("openai")
    client = FakeClient(lambda method, url, body: FakeResponse(data={"data": [{"b64_json": _b64(picture)}]}))
    made = OpenAIImageGenerator("gpt-image-2", api_key=KEY, client=client).generate(REQUEST)

    method, url, body, headers = client.requests[0]
    assert (method, url) == ("POST", "https://api.openai.com/v1/images/generations")
    assert body["model"] == "gpt-image-2" and body["size"] == "1536x1024" and body["quality"] == "low"
    assert body["prompt"] == "a cat wearing sunglasses. Style: a photograph. Avoid: logos."
    assert "seed" not in body  # (OpenAI's image models take none)
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert made.data == picture and made.media_type == "image/png" and made.model == "openai:gpt-image-2"


def test_openai_turns_a_prompt_down_with_its_moderations_categories():
    refusal = {
        "error": {
            "code": "moderation_blocked",
            "type": "image_generation_user_error",
            "message": "Your request was rejected",
            "moderation_details": {"moderation_stage": "input", "categories": ["violence"]},
        }
    }
    client = FakeClient(lambda method, url, body: FakeResponse(400, refusal))
    with pytest.raises(GenerationRefused) as refused:
        OpenAIImageGenerator(api_key=KEY, client=client).generate(REQUEST)
    assert "openai: violence" in refused.value.flags


@pytest.mark.parametrize(
    "status, error",
    [
        (401, GeneratorUnavailable),
        (402, GeneratorUnavailable),
        (429, GenerationRateLimited),
        (500, GeneratorUnavailable),
    ],
)
def test_a_providers_errors_become_generation_errors_without_the_key(status, error):
    said = {"error": {"message": f"Incorrect API key provided: {KEY}"}}
    client = FakeClient(lambda method, url, body: FakeResponse(status, said))
    with pytest.raises(error) as raised:
        OpenAIImageGenerator(api_key=KEY, client=client).generate(REQUEST)
    assert KEY not in str(raised.value)


def test_an_account_without_credits_needs_credits_rather_than_a_wait():
    # (as OpenAI answered on 2026-11-07, for a key whose account had none left)
    said = {
        "error": {
            "code": "insufficient_quota",
            "type": "credit_balance_exhausted",
            "message": "You have no credits remaining. Add credits to continue using the API.",
        }
    }
    client = FakeClient(lambda method, url, body: FakeResponse(429, said))
    with pytest.raises(GeneratorUnavailable, match="needs more credits") as raised:
        OpenAIImageGenerator(api_key=KEY, client=client).generate(REQUEST)
    assert not isinstance(raised.value, GenerationRateLimited)


def test_a_generator_without_its_key_is_unavailable():
    for made in (OpenAIImageGenerator(), GeminiImageGenerator(), FluxImageGenerator(), OpenRouterImageGenerator()):
        with pytest.raises(GeneratorUnavailable, match="key"):
            made.generate(REQUEST)


def _openrouter_server(picture, parameters, pricing=()):
    def answer(method, url, body):
        if method == "GET":
            endpoint = {
                "supported_parameters": {name: {"type": "enum"} for name in parameters},
                "pricing": list(pricing),
            }
            return FakeResponse(data={"id": url, "endpoints": [endpoint]})
        return FakeResponse(
            data={"data": [{"b64_json": _b64(picture), "media_type": "image/png"}], "usage": {"cost": 0.009}}
        )

    return answer


def test_openrouter_asks_once_which_parameters_a_model_takes_and_sends_only_those():
    forget_openrouter()
    picture = _png("openrouter")
    pricing = [{"billable": "output_image", "unit": "image", "cost_usd": 0.011, "variant": "1k"}]
    client = FakeClient(_openrouter_server(picture, ["resolution", "aspect_ratio", "seed", "output_format"], pricing))
    painter = OpenRouterImageGenerator("example/klein", api_key=KEY, client=client)

    assert painter.capabilities.seed and not painter.capabilities.instructions
    assert painter.estimate_cost(REQUEST) == 0.011  # (not in the list prices: as OpenRouter says)
    made = painter.generate(REQUEST)
    painter.generate(REQUEST)

    asked = [request for request in client.requests if request[0] == "GET"]
    assert len(asked) == 1 and asked[0][1].endswith("/images/models/example/klein/endpoints")
    body = client.requests[1][2]
    assert body["resolution"] == "1K" and body["seed"] == 7 and body["aspect_ratio"] == "3:2"
    assert "quality" not in body and "Avoid" not in body["prompt"]  # (a diffusion model would draw what it names)
    assert made.cost_usd == 0.009 and made.data == picture
    forget_openrouter()


def test_openrouters_default_is_gpt_image_2_at_low_quality():
    forget_openrouter()
    client = FakeClient(_openrouter_server(_png("router"), ["aspect_ratio", "quality", "output_format"]))
    painter = OpenRouterImageGenerator(api_key=KEY, client=client)
    painter.generate(REQUEST)
    body = client.requests[-1][2]
    assert (
        painter.id == "openrouter:openai/gpt-image-2" and body["quality"] == "low" and "Avoid: logos" in body["prompt"]
    )
    assert painter.estimate_cost(REQUEST) == 0.006
    forget_openrouter()


def test_gemini_asks_for_an_image_and_skips_its_drafts():
    draft, picture = _png("draft"), _png("gemini")
    answer = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"inlineData": {"mimeType": "image/png", "data": _b64(draft)}, "thought": True},
                        {"text": "Here it is"},
                        {"inlineData": {"mimeType": "image/png", "data": _b64(picture)}},
                    ]
                },
                "finishReason": "STOP",
            }
        ]
    }
    client = FakeClient(lambda method, url, body: FakeResponse(data=answer))
    made = GeminiImageGenerator(api_key=KEY, client=client).generate(REQUEST)
    _, url, body, headers = client.requests[0]
    assert url.endswith("/models/gemini-3.1-flash-lite-image:generateContent") and headers["x-goog-api-key"] == KEY
    assert body["generationConfig"] == {
        "responseModalities": ["IMAGE"],
        "imageConfig": {"aspectRatio": "3:2", "imageSize": "1K"},
        "seed": 7,
    }
    assert made.data == picture


@pytest.mark.parametrize(
    "answer",
    [{"promptFeedback": {"blockReason": "SAFETY"}}, {"candidates": [{"finishReason": "IMAGE_SAFETY", "content": {}}]}],
)
def test_gemini_turns_a_prompt_or_a_picture_down(answer):
    client = FakeClient(lambda method, url, body: FakeResponse(data=answer))
    with pytest.raises(GenerationRefused):
        GeminiImageGenerator(api_key=KEY, client=client).generate(REQUEST)


def _flux_server(picture, statuses):
    statuses = list(statuses)

    def answer(method, url, body):
        if method == "POST":
            return FakeResponse(
                data={"id": "task", "polling_url": "https://api.bfl.ai/v1/get_result?id=task", "cost": 0.9}
            )
        if "get_result" in url:
            status = statuses.pop(0)
            result = {"sample": "https://delivery.bfl.ai/picture.jpg"} if status == "Ready" else None
            return FakeResponse(data={"id": "task", "status": status, "result": result})
        return FakeResponse(content=picture)

    return answer


def test_flux_polls_for_its_picture_and_says_what_it_cost():
    picture = _png("flux")
    client = FakeClient(_flux_server(picture, ["Pending", "Generating", "Ready"]))
    waited = []
    made = FluxImageGenerator("flux-3-image-klein", api_key=KEY, client=client, sleep=waited.append).generate(REQUEST)
    body = client.requests[0][2]
    assert client.requests[0][1] == "https://api.bfl.ai/v1/flux-3-image-klein" and client.requests[0][3]["x-key"] == KEY
    assert body["aspect_ratio"] == "3:2" and body["resolution"] == "1k" and body["seed"] == 7
    assert "Avoid" not in body["prompt"] and body["safety_tolerance"] == 2
    assert made.data == picture and made.cost_usd == pytest.approx(0.009) and len(waited) == 2


def test_flux_2_models_take_a_width_and_a_height_and_moderation_turns_a_picture_down():
    client = FakeClient(_flux_server(_png("flux2"), ["Content Moderated"]))
    painter = FluxImageGenerator("flux-2-klein-4b", api_key=KEY, client=client, sleep=lambda seconds: None)
    with pytest.raises(GenerationRefused):
        painter.generate(REQUEST)
    assert (client.requests[0][2]["width"], client.requests[0][2]["height"]) == (1248, 832)


def test_comfyui_runs_its_first_checkpoint_in_a_text_to_image_workflow():
    picture = _png("comfyui")

    def answer(method, url, body):
        if "object_info" in url:
            return FakeResponse(
                data={"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["sdxl.safetensors"]]}}}}
            )
        if url.endswith("/prompt"):
            return FakeResponse(data={"prompt_id": "abc", "number": 1, "node_errors": {}})
        if "/history/" in url:
            images = [{"filename": "talkgenerator_00001_.png", "subfolder": "", "type": "output"}]
            return FakeResponse(data={"abc": {"outputs": {"7": {"images": images}}, "status": {"completed": True}}})
        return FakeResponse(content=picture)

    client = FakeClient(answer)
    painter = ComfyUIGenerator(url="http://127.0.0.1:8188", client=client, sleep=lambda seconds: None)
    made = painter.generate(REQUEST)
    workflow = next(body for method, url, body, _ in client.requests if url.endswith("/prompt"))["prompt"]
    assert painter.id == "comfyui:sdxl.safetensors" and painter.capabilities.local
    assert workflow["1"]["inputs"]["ckpt_name"] == "sdxl.safetensors"
    assert workflow["5"]["inputs"]["seed"] == 7 and workflow["4"]["inputs"]["width"] == 1216
    assert workflow["3"]["inputs"]["text"] == "logos"  # (what to avoid: the negative prompt)
    assert made.data == picture and made.cost_usd == 0.0
    assert painter.estimate_cost(REQUEST) == 0.0


def test_automatic1111_gets_a_negative_prompt_and_switches_only_to_a_checkpoint_it_is_given():
    picture = _png("a1111")

    def answer(method, url, body):
        if url.endswith("/options"):
            return FakeResponse(data={"sd_model_checkpoint": "dreamshaper"})
        return FakeResponse(data={"images": [_b64(picture)]})

    def last_post(client):
        return next(body for method, url, body, _ in reversed(client.requests) if method == "POST")

    client = FakeClient(answer)
    own = Automatic1111Generator(url="http://127.0.0.1:7860", client=client)
    made = own.generate(REQUEST)
    assert made.data == picture and made.model == own.id == "automatic1111:dreamshaper"
    body = last_post(client)
    assert body["negative_prompt"] == "logos" and body["seed"] == 7 and "override_settings" not in body
    Automatic1111Generator("juggernaut", url="http://127.0.0.1:7860", client=client).generate(REQUEST)
    assert last_post(client)["override_settings"] == {"sd_model_checkpoint": "juggernaut"}


def test_a_local_server_that_is_down_makes_no_picture_and_no_trouble():
    client = FakeClient(lambda method, url, body: None)  # (nothing answers)
    for painter in (ComfyUIGenerator(client=client, sleep=lambda seconds: None), Automatic1111Generator(client=client)):
        assert painter.id.endswith(":server")  # (and the talk's estimate can name it)
        with pytest.raises(GeneratorUnavailable, match="can't be reached"):
            painter.generate(REQUEST)


def test_generators_come_from_specs_and_a_key_alone_makes_none(monkeypatch):
    assert generator_from_spec("none") is None and generator_from_spec(None) is None
    assert generator_from_spec("openai").id == "openai:gpt-image-2"
    assert generator_from_spec("gemini:gemini-3-pro-image").id == "gemini:gemini-3-pro-image"
    assert generator_from_spec("flux").id == "flux:flux-3-image-klein"
    with pytest.raises(ValueError, match="no image generator"):
        generator_from_spec("midjourney")
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    assert settings.image_generator_spec() == "none"
    monkeypatch.setenv("TALKGENERATOR_IMAGE_GENERATOR", "openai")
    assert settings.image_generator_spec() == "openai"
    monkeypatch.setenv("DISABLE_IMAGE_GENERATION", "1")
    assert settings.image_generator_spec() == "none"


def test_prices_come_from_config_and_the_config_folders_file_changes_them(tmp_path, monkeypatch):
    assert prices.price_of("openai:gpt-image-2", "low") == 0.006
    assert prices.price_of("openai:gpt-image-2", "high") == 0.211
    assert prices.price_of("flux:flux-3-image-klein") == 0.009
    assert prices.price_of("openai:gpt-image-9") is None
    assert prices.retiring("gemini:gemini-2.5-flash-image") == "2027-03-15"
    monkeypatch.setenv("TALKGENERATOR_CONFIG_DIR", str(tmp_path))
    (tmp_path / prices.FILE_NAME).write_text(
        json.dumps({"providers": {"openai": {"default": "gpt-image-9", "prices": {"gpt-image-9": {"low": 0.002}}}}}),
        encoding="utf-8",
    )
    assert prices.price_of("openai:gpt-image-9") == 0.002 and prices.price_of("openai:gpt-image-2") == 0.006
    assert generator_from_spec("openai").id == "openai:gpt-image-9"


# THE RULES


@pytest.mark.parametrize(
    "prompt",
    [
        "Albert Einstein juggling peanuts",
        "a portrait of Einstein in a lab",
        "Donald Trump eating a sandwich",
        "Pikachu at a board meeting",
        "a Coca-Cola can on the moon",
        "a company logo made of cheese",
        "a celebrity at a cheese tasting",
        "a gory scene in a kitchen",
        "a nude statue of a penguin",
        "a church full of cats",
    ],
)
def test_prompts_that_break_the_rules_are_never_sent(prompt):
    assert safety.screen(prompt) is not None


@pytest.mark.parametrize(
    "prompt",
    [
        "a cat wearing sunglasses on a bicycle",
        "an old photograph of monks testing peanut butter in a monastery kitchen",
        "the cover of a book titled 'The Secret Life of Spoons'",
        "a made-up Victorian inventor with an enormous moustache",
    ],
)
def test_ordinary_prompts_may_be_sent(prompt):
    assert safety.screen(prompt) is None


def test_a_prompt_with_the_presenters_name_is_never_sent():
    assert safety.screen("Ann Example riding a camel", private=["Ann Example"]) is not None
    assert safety.screen("a camel at sunset", private=["Ann Example"]) is None


def test_a_talk_on_a_sensitive_topic_generates_nothing():
    assert safety.screen_topic(["peanuts"]) is None
    assert safety.screen_topic(["terrorism"]) is not None


# THE CACHE


def test_the_cache_keeps_pictures_by_model_prompt_shape_and_seed():
    request = REQUEST
    assert cache.key("a:b", request, seeded=True) != cache.key("a:b", request.model_copy(update={"seed": 8}), True)
    # (a generator without seeds makes the same picture whatever the seed)
    assert cache.key("a:b", request, seeded=False) == cache.key("a:b", request.model_copy(update={"seed": 8}), False)
    assert cache.key("a:b", request, True) != cache.key("a:c", request, True)
    image = GeneratedImage(data=_png("kept"), media_type="image/png", model="a:b", cost_usd=0.01)
    path = cache.put("abc", image, request)
    assert path.parent == cache.folder() and path.suffix == ".png"
    kept_path, kept = cache.get("abc")
    assert kept_path == path and kept.data == image.data and kept.model == "a:b" and kept.cost_usd == 0.01
    assert cache.get("nothing") is None


# TALKS THAT GENERATE PICTURES


class FakePainter(ImageGenerator):
    """Paints a picture of its own for every request (the same for the same request), remembers what it was asked,
    and turns down prompts with any of the words in `refuse`."""

    capabilities = GeneratorCapabilities(seed=True, instructions=True)
    terms = ("the fake painter's terms", "https://painter.example/terms")

    def __init__(self, price=0.01, refuse=()):
        self.id = "fake:painter"
        self.price = price
        self.refuse = refuse
        self.requests = []
        self._lock = threading.Lock()

    def generate(self, request):
        with self._lock:
            self.requests.append(request)
        if any(word in request.prompt for word in self.refuse):
            raise GenerationRefused("the fake painter won't", ("fake: moderated",))
        seed = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        return GeneratedImage(data=_png(seed), media_type="image/png", model=self.id, seed=request.seed)

    def estimate_cost(self, request):
        return self.price


class FailingPainter(FakePainter):
    def generate(self, request):
        super().generate(request)
        raise GenerationError("the fake painter's server is down")


def _stock(name):
    return ImageData(
        f"https://images/{name}.jpg", source=f"{name} (fake)", license_class="stock", declared_size=(1600, 1000)
    )


class StockSource:
    """A source of stock photos named after the query, that finds nothing for a query with "nothing" in it."""

    def __init__(self):
        self.asked = []

    def search(self, search):
        self.asked.append(search.query)
        if "nothing" in search.query:
            return []
        return [(1.0, _stock(f"{search.query.replace(' ', '_')}-{n}")) for n in range(4)]


@pytest.fixture(autouse=True)
def pictures(monkeypatch):
    """Images at https://images/ exist (and probes find them, as they find generated pictures, local files)."""
    jpeg = _png("stock")
    load = image_util.fetch_image
    monkeypatch.setattr(image_util, "fetch_image", lambda url: jpeg if url.startswith("https://images/") else load(url))
    monkeypatch.setattr(image_util, "probe", lambda url: url.startswith("https://images/") or os.path.isfile(url))


@pytest.fixture
def stock(monkeypatch):
    source = StockSource()
    monkeypatch.setitem(
        catalog.SOURCES,
        "fake-stock",
        catalog.Source("fake-stock", "fake", frozenset({"stock"}), source.search, lambda: True),
    )
    # (looks talkgenerator can draw, on the fake stock photos: their pictures may be generated when none is found)
    for name in ("photo", "meme-chaos"):
        monkeypatch.setitem(profiles.PROFILES, name, Profile(name, "fake", (SourceUse("fake-stock"),)))
    return source


HOBBY = ImageSlot("the presenter's weird hobby", aesthetic="meme-chaos", generate=True)
PHOTO = ImageSlot("a photo of the slide's topic", aesthetic="photo")


def _schema():
    def slide(name, slot, weight, tags):
        return SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(StaticGenerator(name), slot),
            weight_function=ConstantWeightFunction(weight),
            allowed_repeated_elements=1,
            tags=list(tags),
            name=name,
            llm=Recipe("image", (slot,)),
        )

    title = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
        llm=Recipe("title"),
    )
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "Talking about " + context["seed"],
        slide_generators=[title, slide("Hobby", HOBBY, 2, ["hobby"]), slide("Photo", PHOTO, 2, ["photo"])],
        max_allowed_tags={"title": 1},
    )


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    made = _schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    return made


TALK = {"topic": "owls", "presenter": "Ann Example", "int_seed": 3}
SLIDES = 6


def _talk(painter, budget=ImageBudget(3), llm=None, parallel=True, **options):
    _, slide_deck, _ = generator.generate_presentation(
        "fake",
        SLIDES,
        save_ppt=False,
        parallel=parallel,
        llm=llm or FakeModel(),
        image_generator=painter,
        image_budget=budget,
        **{**TALK, **options},
    )
    return slide_deck.to_deck(schema_name="fake")


def _images(deck):
    return [(number, image) for number, slide in enumerate(deck.slides) for image in slide.images()]


def _generated(deck):
    return [(number, image) for number, image in _images(deck) if image.license_class == "generated"]


def test_a_talk_generates_the_pictures_its_slots_prefer_from_the_models_prompts(stock):
    painter = FakePainter()
    deck = _talk(painter)

    generated = _generated(deck)
    hobbies = [
        number
        for number, slide in enumerate(deck.slides)
        if slide.notes.startswith("Seed") and "for Hobby" in slide.notes
    ]
    assert generated and [number for number, _ in generated] == hobbies[: len(generated)]
    for number, image in generated:
        assert image.credit[0].text == "AI-generated with painter" and image.source == "AI-generated with painter"
        assert (
            image.display == "copy" and os.path.isfile(image.url) and os.path.dirname(image.url) == str(cache.folder())
        )
        assert image.license == "the fake painter's terms" and image.description.startswith("image prompt of slide ")
        assert deck.slides[number].credits[0][0].text == "AI-generated with painter"
    # Every other picture is a stock photo, and the photo slides' pictures aren't generated
    assert all(image.license_class == "stock" for _, image in _images(deck) if image.license_class != "generated")
    request = painter.requests[0]
    assert request.prompt.startswith("image prompt of slide ") and request.seed is not None
    assert (
        request.style == generation.STYLES["meme-chaos"] and "logos" in request.avoid and request.aspect_ratio == "4:3"
    )
    assert deck.usage.images == len(painter.requests) == len(generated) and deck.usage.image_cost_usd == pytest.approx(
        0.01 * len(generated)
    )
    assert deck.usage.requests == 1  # (one language model request: a picture isn't one)
    assert check_licenses(deck) == []


def test_the_model_writes_prompts_only_in_a_talk_that_generates(stock):
    with_painter, without = FakeModel(), FakeModel()
    _talk(FakePainter(), llm=with_painter)
    _talk(None, llm=without)
    schema_with = json.dumps(with_painter.requests[0].json_schema)
    assert "image_prompt" in schema_with and "image_prompt" not in json.dumps(without.requests[0].json_schema)
    assert "image_prompt" not in json.dumps(without.requests[0].messages[0].content)


def test_a_talk_generates_a_few_pictures_at_most_in_the_order_of_its_slides(stock):
    painter = FakePainter()
    one = _generated(_talk(painter, budget=ImageBudget(1)))
    everything = _generated(_talk(FakePainter(), budget=ImageBudget(10)))
    assert len(everything) > 1 and len(one) == 1 and one[0] == everything[0]
    assert len(painter.requests) == 1


def _without_image_usage(deck):
    """The deck, as if its pictures had all come from the cache (a talk made again pays for none of them)."""
    return deck.model_copy(update={"usage": deck.usage.model_copy(update={"images": 0, "image_cost_usd": 0.0})})


@pytest.mark.parametrize("seed", [3, 4])
def test_the_same_seed_generates_the_same_pictures_in_parallel_or_one_by_one_and_then_from_the_cache(stock, seed):
    first, again = FakePainter(), FakePainter()
    in_parallel = _talk(first, int_seed=seed, parallel=True)
    one_by_one = _talk(again, int_seed=seed, parallel=False)
    assert _generated(in_parallel) and _generated(in_parallel) == _generated(one_by_one)
    assert first.requests and not again.requests  # (the second talk's pictures came from the cache)
    assert one_by_one.usage.images == 0 and one_by_one.usage.image_cost_usd == 0.0
    assert _without_image_usage(in_parallel).to_json() == one_by_one.to_json()


def test_a_streamed_talk_hands_a_slide_over_again_once_its_generated_picture_is_in(stock):
    painter = FakePainter()
    events = list(
        generator.stream_talk("fake", SLIDES, llm=FakeModel(), image_generator=painter, theme="clean keynote", **TALK)
    )
    ready = [event for event in events if isinstance(event, SlideReady)]
    updated = [event for event in events if isinstance(event, SlideUpdated)]
    finished = events[-1]
    assert isinstance(finished, TalkFinished) and updated
    assert events.index(updated[0]) > events.index(ready[0])
    for event in updated:
        before = next(earlier for earlier in ready if earlier.index == event.index)
        assert [image.license_class for image in before.slide.images()] == ["stock"]
        assert [image.license_class for image in event.slide.images()] == ["generated"]
        assert event.slide.layout == before.slide.layout and event.slide.layout.startswith("v5/")
    # The slides as last handed over are the deck's, which is the deck made at once
    latest = {event.index: event.slide for event in ready}
    latest.update({event.index: event.slide for event in updated})
    assert [latest[index] for index in sorted(latest)] == list(finished.deck.slides)
    # (made at once, its pictures come from the cache)
    assert _without_image_usage(finished.deck).to_json() == _talk(FakePainter(), theme="clean keynote").to_json()


def _unfindable(answer):
    """The model's queries and concepts for its photo slides find nothing."""
    for key, value in answer.items():
        if (
            key.startswith("slide_")
            and isinstance(value, dict)
            and "image_query" in value
            and "image_prompt" not in value
        ):
            value["image_query"] = "nothing at all"
            value["concept"] = "nothing either"


def test_a_slide_whose_search_finds_nothing_gets_a_generated_picture_on_its_last_try(stock):
    painter = FakePainter()
    deck = _talk(painter, budget=ImageBudget(10), llm=FakeModel(change=_unfindable))
    photos = [slide for slide in deck.slides if "for Photo" in slide.notes]
    assert photos and all(image.license_class == "generated" for slide in photos for image in slide.images())
    assert any("nothing at all" in request.prompt for request in painter.requests)
    # Without pictures to generate, they're classic slides
    classic = _talk(FakePainter(), budget=ImageBudget(0), llm=FakeModel(change=_unfindable))
    assert not _generated(classic) and not [slide for slide in classic.slides if "for Photo" in slide.notes]


def test_a_refused_or_failed_picture_keeps_its_stock_photo(stock):
    refusing = FakePainter(refuse=("of slide",))
    deck = _talk(refusing)
    assert refusing.requests and not _generated(deck)
    assert deck.usage.failed_images == len(refusing.requests) and deck.usage.images == 0
    failing = FailingPainter()
    assert not _generated(_talk(failing)) and failing.requests


def test_a_prompt_that_breaks_the_rules_is_never_sent(stock):
    def famous(answer):
        for value in answer.values():
            if isinstance(value, dict) and "image_prompt" in value:
                value["image_prompt"] = "Albert Einstein juggling owls"

    painter = FakePainter()
    assert not _generated(_talk(painter, llm=FakeModel(change=famous))) and not painter.requests


def test_talks_that_generate_no_pictures(stock):
    painter = FakePainter()
    _talk(painter, llm="none")  # (classic: no texts to say what a picture is to show)
    _talk(painter, license_policy="public-domain,open,stock")  # (no generated pictures allowed)
    _talk(painter, topic="terrorism")  # (a topic a slide shouldn't make light of)
    _talk(painter, budget=ImageBudget(3, max_cost_usd=0.0))  # (a paid one, on a budget of free ones only)
    assert not painter.requests
    unpriced = FakePainter(price=None)
    _talk(unpriced, budget=ImageBudget(3, max_cost_usd=1.0))  # (its price isn't known, and the budget has dollars)
    assert not unpriced.requests


def test_the_settings_generator_paints_but_never_in_a_benchmark(stock, monkeypatch):
    from talkgenerator.checks import benchmark
    from talkgenerator.images.generators import providers

    painter = FakePainter()
    monkeypatch.setitem(providers._FACTORIES, "fake-painter", lambda model: painter)
    monkeypatch.setenv("TALKGENERATOR_IMAGE_GENERATOR", "fake-painter")
    assert _generated(_talk(None)) and painter.requests  # (TALKGENERATOR_IMAGE_GENERATOR's)
    asked = len(painter.requests)
    benchmark.generate_deck("owls", 3, "fake", SLIDES, True, llm=FakeModel())
    assert len(painter.requests) == asked
    monkeypatch.setenv("DISABLE_IMAGE_GENERATION", "1")
    assert not _generated(_talk(FakePainter()))  # (the switch stops a generator that's given, too)


def test_a_dollar_limit_keeps_to_the_list_prices(stock):
    painter = FakePainter(price=0.01)
    assert len(_generated(_talk(painter, budget=ImageBudget(10, max_cost_usd=0.015)))) == 1


def test_a_deck_with_generated_pictures_renders_again_without_generating(stock):
    painter = FakePainter()
    deck = Deck.from_json(_talk(painter).to_json())
    asked = len(painter.requests)
    presentation = render_pptx(deck)
    assert len(painter.requests) == asked
    embedded = {shape.image.blob for slide in presentation.slides for shape in slide.shapes if hasattr(shape, "image")}
    kept = {open(image.url, "rb").read() for _, image in _generated(deck)}
    assert kept and kept <= embedded


def test_the_estimate_says_what_a_talks_pictures_may_cost():
    assert str(generation.estimate("openai", ImageBudget(3))) == (
        "up to 3 pictures with openai:gpt-image-2, at about $0.0060 each: $0.0180 at most"
    )
    assert "for nothing" in str(generation.estimate(ComfyUIGenerator("sdxl"), ImageBudget(2)))
    assert generation.estimate("none").images == 0
